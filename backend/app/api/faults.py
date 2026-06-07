"""Arıza kaydı uçları: tekil ekleme, CSV toplu içe aktarma, id ile okuma."""

from __future__ import annotations

import csv
import io
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.deps import get_current_user, get_engine, require_admin
from app.schemas import FaultCreate, FaultRead
from app.services.memory_store import FaultRecord, MemoryEngine

router = APIRouter(prefix="/api/faults", tags=["faults"])


def _to_read(record: FaultRecord) -> FaultRead:
    return FaultRead(
        fault_id=record.id,
        description=record.description,
        category=record.category,
        solution=record.solution,
        dtc_code=record.dtc_code,
        vehicle_model=record.vehicle_model,
        mileage_km=record.mileage_km,
    )


@router.post("", response_model=FaultRead, status_code=201)
def create_fault(
    payload: FaultCreate,
    engine: MemoryEngine = Depends(get_engine),
    _admin=Depends(require_admin),
) -> FaultRead:
    """Yeni bir arıza kaydı ekle (yalnız admin)."""
    record = FaultRecord(
        id=str(uuid4()),
        description=payload.description.strip(),
        category=payload.category.strip(),
        dtc_code=(payload.dtc_code or None),
        vehicle_model=(payload.vehicle_model or None),
        mileage_km=payload.mileage_km,
        solution=payload.solution.strip(),
    )
    engine.add(record)
    return _to_read(record)


@router.post("/import")
async def import_csv(
    file: UploadFile,
    engine: MemoryEngine = Depends(get_engine),
    _admin=Depends(require_admin),
) -> dict:
    """CSV'den toplu kayıt yükle (yalnız admin; description/category/solution zorunlu)."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Dosya UTF-8 değil.") from exc

    reader = csv.DictReader(io.StringIO(text))
    added = 0
    skipped = 0
    for row in reader:
        description = (row.get("description") or "").strip()
        category = (row.get("category") or "").strip()
        solution = (row.get("solution") or "").strip()
        if not (description and category and solution):
            skipped += 1
            continue
        mileage = (row.get("mileage_km") or "").strip()
        engine.add(
            FaultRecord(
                id=str(uuid4()),
                description=description,
                category=category,
                dtc_code=(row.get("dtc_code") or "").strip() or None,
                vehicle_model=(row.get("vehicle_model") or "").strip() or None,
                mileage_km=int(mileage) if mileage.isdigit() else None,
                solution=solution,
            )
        )
        added += 1

    return {"added": added, "skipped": skipped, "total": engine.count}


@router.get("/{fault_id}", response_model=FaultRead)
def get_fault(
    fault_id: str,
    engine: MemoryEngine = Depends(get_engine),
    _user=Depends(get_current_user),
) -> FaultRead:
    """Tek bir arıza kaydını id ile getir (oturum açmış kullanıcı)."""
    record = engine.get(fault_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
    return _to_read(record)
