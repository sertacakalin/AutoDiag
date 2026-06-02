import { useEffect, useState } from "react";
import { addFault, ApiError } from "../api/client";
import type { FaultRead } from "../api/types";
import styles from "./AddFaultDrawer.module.css";

interface Props {
  open: boolean;
  categories: string[];
  onClose: () => void;
  onCreated: (fault: FaultRead) => void;
}

const EMPTY = {
  description: "",
  category: "",
  solution: "",
  dtc_code: "",
  vehicle_model: "",
  mileage_km: "",
};

export function AddFaultDrawer({ open, categories, onClose, onCreated }: Props) {
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Esc ile kapat.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const valid =
    form.description.trim().length >= 3 &&
    form.category.trim().length > 0 &&
    form.solution.trim().length >= 3;

  function set<K extends keyof typeof EMPTY>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submit() {
    if (!valid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const created = await addFault({
        description: form.description.trim(),
        category: form.category.trim(),
        solution: form.solution.trim(),
        dtc_code: form.dtc_code.trim() || null,
        vehicle_model: form.vehicle_model.trim() || null,
        mileage_km: form.mileage_km.trim() ? Number(form.mileage_km) : null,
      });
      setForm({ ...EMPTY });
      onCreated(created);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Kayıt eklenemedi.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.scrim} onMouseDown={onClose}>
      <div
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-label="Yeni arıza kaydı"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className={styles.head}>
          <div>
            <h2 className={styles.title}>Yeni arıza kaydı</h2>
            <p className={styles.lead}>
              Çözülmüş bir vakayı bilgi tabanına ekleyin; sonraki aramalarda
              referans olur.
            </p>
          </div>
          <button className={styles.close} onClick={onClose} aria-label="Kapat">
            ✕
          </button>
        </header>

        <div className={styles.body}>
          <Field label="Arıza tanımı" required>
            <textarea
              className={styles.textarea}
              rows={3}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              placeholder="Belirtiler ve gözlemler…"
            />
          </Field>

          <div className={styles.row}>
            <Field label="Kategori" required>
              <select
                className={styles.input}
                value={form.category}
                onChange={(e) => set("category", e.target.value)}
              >
                <option value="">Seçiniz…</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="DTC kodu">
              <input
                className={`${styles.input} ${styles.mono}`}
                value={form.dtc_code}
                onChange={(e) => set("dtc_code", e.target.value.toUpperCase())}
                placeholder="P0300"
                maxLength={8}
              />
            </Field>
          </div>

          <Field label="Uygulanan çözüm" required>
            <textarea
              className={styles.textarea}
              rows={3}
              value={form.solution}
              onChange={(e) => set("solution", e.target.value)}
              placeholder="Yapılan işlem ve sonuç…"
            />
          </Field>

          <div className={styles.row}>
            <Field label="Araç modeli">
              <input
                className={styles.input}
                value={form.vehicle_model}
                onChange={(e) => set("vehicle_model", e.target.value)}
                placeholder="Renault Megane"
              />
            </Field>
            <Field label="Kilometre">
              <input
                className={styles.input}
                value={form.mileage_km}
                onChange={(e) =>
                  set("mileage_km", e.target.value.replace(/\D/g, ""))
                }
                placeholder="142000"
                inputMode="numeric"
              />
            </Field>
          </div>

          {error && <p className={styles.error}>{error}</p>}
        </div>

        <footer className={styles.foot}>
          <button className={styles.cancel} onClick={onClose}>
            Vazgeç
          </button>
          <button
            className={styles.save}
            onClick={submit}
            disabled={!valid || saving}
          >
            {saving ? "Kaydediliyor…" : "Kaydı ekle"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>
        {label}
        {required && <span className={styles.req}>*</span>}
      </span>
      {children}
    </label>
  );
}
