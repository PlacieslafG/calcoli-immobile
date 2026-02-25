import customtkinter as ctk
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
from datetime import datetime

# ── Palette colori scenario ────────────────────────────────────────────────────
SCENARIO_COLORS = [
    "#1a5276", "#1e8449", "#6e2fa0", "#a04000", "#145a72", "#7d6608",
]

# ── Tema ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ── Helpers ───────────────────────────────────────────────────────────────────
def to_float(value: str) -> float:
    try:
        return float(value.replace(",", ".").strip())
    except (ValueError, AttributeError):
        return 0.0


def fmt_eur(value: float) -> str:
    return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pol_breakdown(imp: float, mode: str, n_mesi: float):
    """Restituisce (mensile, annuale, tot_durata, unica)."""
    if mode == "In rata":
        return imp, 0.0, imp * n_mesi, 0.0
    elif mode == "Annuale":
        return imp / 12, imp, imp / 12 * n_mesi, 0.0
    else:  # Unica soluzione
        return 0.0, 0.0, imp, imp


def _pol_line(imp: float, mode: str, mensile: float) -> str:
    if imp == 0:
        return "non inserita"
    if mode == "In rata":
        return f"{fmt_eur(imp)}/mese (in rata)"
    elif mode == "Annuale":
        return f"{fmt_eur(imp)}/anno  (≈ {fmt_eur(mensile)}/mese)"
    else:
        return f"{fmt_eur(imp)} unica soluzione"


def calcola_taeg(
    importo: float,
    upfront_costs: float,
    rata_base: float,
    n: int,
    pol_si_imp: float,
    pol_si_mode: str,
) -> float | None:
    """
    TAEG (EU Mortgage Credit Directive).
    Risolve: (importo - upfront_costs) = Σ CF_k / (1+r)^k  per r mensile.
    Ritorna il tasso annuale effettivo globale in percentuale, o None se non calcolabile.
    Inclusi nei CF: rata_base + pol. scoppio/incendio (obbligatoria).
    Upfront: istruttoria + perizia + imp. sostitutiva + pol. unica scoppio/incendio.
    """
    net = importo - upfront_costs
    if net <= 0 or n <= 0 or rata_base <= 0:
        return None

    cfs = []
    for k in range(1, int(n) + 1):
        cf = rata_base
        if pol_si_mode == "In rata":
            cf += pol_si_imp
        elif pol_si_mode == "Annuale" and k % 12 == 0:
            cf += pol_si_imp
        cfs.append(cf)

    def npv(mr: float) -> float:
        return sum(c / (1 + mr) ** k for k, c in enumerate(cfs, 1)) - net

    try:
        lo, hi = 1e-9, 0.5
        if npv(lo) * npv(hi) > 0:
            return None
        for _ in range(120):
            mid = (lo + hi) / 2
            if npv(mid) > 0:
                lo = mid
            else:
                hi = mid
        return ((1 + (lo + hi) / 2) ** 12 - 1) * 100
    except Exception:
        return None


# ── Widget helpers ─────────────────────────────────────────────────────────────
def _lbl(parent, text, row, col=0, padx=(0, 12), pady=4, **kw):
    ctk.CTkLabel(parent, text=text, anchor="w", **kw).grid(
        row=row, column=col, padx=padx, pady=pady, sticky="w"
    )


def _entry(parent, row, col, default, width=140):
    e = ctk.CTkEntry(parent, width=width)
    e.insert(0, default)
    e.grid(row=row, column=col, pady=4, sticky="w")
    return e


def _seg(parent, values, var, row, col, width=240, padx=(0, 0), command=None):
    kw = {"command": command} if command else {}
    ctk.CTkSegmentedButton(
        parent, values=values, variable=var, width=width, **kw
    ).grid(row=row, column=col, columnspan=len(values), padx=padx, pady=4, sticky="w")


# ── Classe scenario mutuo ──────────────────────────────────────────────────────
class MutuoWidget(ctk.CTkFrame):
    """Un blocco mutuo autonomo con tutti i suoi campi."""

    def __init__(self, parent, index: int, on_remove, get_prezzo,
                 defaults: dict | None = None, **kw):
        super().__init__(parent, **kw)
        self._index = index
        self._on_remove = on_remove
        self._get_prezzo = get_prezzo
        self._defaults = defaults or {}
        self._build()

    def set_index(self, index: int):
        self._index = index  # name entry unchanged: user controls it

    def _build(self):
        color = SCENARIO_COLORS[self._index % len(SCENARIO_COLORS)]

        # ── Intestazione scenario ──────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=color, corner_radius=6)
        header.pack(fill="x", padx=0, pady=(0, 8))

        self._entry_nome = ctk.CTkEntry(
            header,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="white",
            fg_color="transparent",
            border_width=0,
            width=220,
        )
        self._entry_nome.insert(0, f"Scenario {self._index + 1}")
        self._entry_nome.pack(side="left", padx=10, pady=6)

        ctk.CTkButton(
            header, text="✕ Rimuovi", width=90, height=26,
            fg_color="#c0392b", hover_color="#96281b",
            font=ctk.CTkFont(size=11),
            command=lambda: self._on_remove(self),
        ).pack(side="right", padx=8, pady=4)

        # ── Grid dei campi ─────────────────────────────────────────────────
        g = ctk.CTkFrame(self, fg_color="transparent")
        g.pack(padx=12, pady=(0, 10), fill="x")

        # Modalità importo
        _lbl(g, "Modalità importo:", 0)
        self.mutuo_mode = ctk.StringVar(value="€ Importo")
        _seg(g, ["€ Importo", "% Prezzo"], self.mutuo_mode, 0, 1,
             width=200, command=self._on_mode_change)

        # Importo / percentuale
        self._lbl_imp = ctk.CTkLabel(g, text="Importo mutuo", anchor="w")
        self._lbl_imp.grid(row=1, column=0, padx=(0, 12), pady=4, sticky="w")
        self.e_importo = _entry(g, 1, 1, "160000")
        self._lbl_unit = ctk.CTkLabel(g, text="€", anchor="w",
                                      text_color=("gray40", "gray60"))
        self._lbl_unit.grid(row=1, column=2, padx=(6, 0), pady=4, sticky="w")

        # Tasso / Durata
        _lbl(g, "Tasso annuo (%):", 2)
        self.e_tasso = _entry(g, 2, 1, "3.50")
        _lbl(g, "Durata (anni):", 3)
        self.e_durata = _entry(g, 3, 1, "25")

        # Separatore
        ctk.CTkFrame(g, height=1, fg_color=("gray70", "gray35")).grid(
            row=4, column=0, columnspan=6, sticky="ew", pady=(8, 4)
        )

        # Polizza scoppio/incendio
        _lbl(g, "Pol. scoppio/incendio (€):", 5)
        self.e_pol_si = _entry(g, 5, 1, "300", width=100)
        self.pol_si_mode = ctk.StringVar(value="Annuale")
        _seg(g, ["In rata", "Annuale", "Unica"], self.pol_si_mode, 5, 2,
             width=240, padx=(8, 0))
        _lbl(g, "obbligatoria", 5, col=5, padx=(8, 0),
             text_color=("gray50", "gray55"))

        # Polizza vita
        _lbl(g, "Polizza vita (€):", 6)
        self.e_pol_v = _entry(g, 6, 1, "0", width=100)
        self.pol_v_mode = ctk.StringVar(value="Annuale")
        _seg(g, ["In rata", "Annuale", "Unica"], self.pol_v_mode, 6, 2,
             width=240, padx=(8, 0))
        _lbl(g, "facoltativa", 6, col=5, padx=(8, 0),
             text_color=("gray50", "gray55"))

        # ── Separatore spese bancarie ──────────────────────────────────────
        ctk.CTkFrame(g, height=1, fg_color=("gray70", "gray35")).grid(
            row=7, column=0, columnspan=6, sticky="ew", pady=(8, 4)
        )
        _lbl(g, "Spese bancarie mutuo", 7, col=0, pady=4,
             font=ctk.CTkFont(size=11, weight="bold"),
             text_color=("gray30", "gray70"))

        # Spese istruttoria
        _lbl(g, "Spese istruttoria (€):", 8)
        self.e_istruttoria = _entry(g, 8, 1, "500", width=100)

        # Spese perizia
        _lbl(g, "Spese perizia (€):", 9)
        self.e_perizia = _entry(g, 9, 1, "300", width=100)

        # Imposta sostitutiva
        _lbl(g, "Imposta sostitutiva:", 10)
        self.imp_sost_mode = ctk.StringVar(value="Prima casa")
        _seg(g, ["Prima casa", "Seconda casa", "€ fisso"],
             self.imp_sost_mode, 10, 1,
             width=280, command=self._on_imp_sost_change)
        self.e_imp_sost = ctk.CTkEntry(g, width=90, state="disabled",
                                       placeholder_text="auto")
        self.e_imp_sost.grid(row=10, column=4, padx=(8, 0), pady=4, sticky="w")
        self._lbl_imp_sost_note = ctk.CTkLabel(
            g, text="0,25% mutuo", anchor="w",
            text_color=("gray50", "gray55"),
            font=ctk.CTkFont(size=11, slant="italic"),
        )
        self._lbl_imp_sost_note.grid(
            row=10, column=5, padx=(6, 0), pady=4, sticky="w"
        )

        self._apply_defaults()

    def get_values(self) -> dict:
        """Restituisce tutti i valori correnti del widget, usato per clonare lo scenario."""
        return {
            "mutuo_mode":    self.mutuo_mode.get(),
            "importo":       self.e_importo.get(),
            "tasso":         self.e_tasso.get(),
            "durata":        self.e_durata.get(),
            "pol_si":        self.e_pol_si.get(),
            "pol_si_mode":   self.pol_si_mode.get(),
            "pol_v":         self.e_pol_v.get(),
            "pol_v_mode":    self.pol_v_mode.get(),
            "istruttoria":   self.e_istruttoria.get(),
            "perizia":       self.e_perizia.get(),
            "imp_sost_mode": self.imp_sost_mode.get(),
            "imp_sost":      self.e_imp_sost.get(),
        }

    def _apply_defaults(self):
        d = self._defaults
        if not d:
            return

        def _set(entry, key):
            if key in d and d[key] != "":
                entry.delete(0, "end")
                entry.insert(0, d[key])

        # StringVar / segmented buttons
        if "mutuo_mode" in d:
            self.mutuo_mode.set(d["mutuo_mode"])
            if d["mutuo_mode"] == "% Prezzo":
                self._lbl_imp.configure(text="Quota mutuo (% prezzo)")
                self._lbl_unit.configure(text="%")
        if "pol_si_mode" in d:
            self.pol_si_mode.set(d["pol_si_mode"])
        if "pol_v_mode" in d:
            self.pol_v_mode.set(d["pol_v_mode"])
        if "imp_sost_mode" in d:
            self.imp_sost_mode.set(d["imp_sost_mode"])
            self._on_imp_sost_change(d["imp_sost_mode"])

        # Entries
        _set(self.e_importo,    "importo")
        _set(self.e_tasso,      "tasso")
        _set(self.e_durata,     "durata")
        _set(self.e_pol_si,     "pol_si")
        _set(self.e_pol_v,      "pol_v")
        _set(self.e_istruttoria, "istruttoria")
        _set(self.e_perizia,    "perizia")
        if d.get("imp_sost_mode") == "€ fisso":
            self.e_imp_sost.configure(state="normal")
            _set(self.e_imp_sost, "imp_sost")

    # ── Modalità imposta sostitutiva ─────────────────────────────────────
    def _on_imp_sost_change(self, value: str):
        if value == "€ fisso":
            self.e_imp_sost.configure(state="normal", placeholder_text="")
            self._lbl_imp_sost_note.configure(text="")
        else:
            self.e_imp_sost.configure(state="disabled", placeholder_text="auto")
            note = "0,25% mutuo" if value == "Prima casa" else "2% mutuo"
            self._lbl_imp_sost_note.configure(text=note)

    # ── Modalità importo ───────────────────────────────────────────────────
    def _on_mode_change(self, value: str):
        prezzo  = self._get_prezzo()
        current = to_float(self.e_importo.get())
        self.e_importo.delete(0, "end")
        if value == "% Prezzo":
            self._lbl_imp.configure(text="Quota mutuo (% prezzo)")
            self._lbl_unit.configure(text="%")
            pct = current / prezzo * 100 if prezzo > 0 and current > 0 else 80
            self.e_importo.insert(0, f"{pct:.1f}")
        else:
            self._lbl_imp.configure(text="Importo mutuo")
            self._lbl_unit.configure(text="€")
            imp = int(current / 100 * prezzo) if prezzo > 0 and current > 0 else 160000
            self.e_importo.insert(0, str(imp))

    # ── Calcola scenario ───────────────────────────────────────────────────
    def calcola(self, prezzo: float, notaio: float, agenzia: float,
                imposta: float, agenzia_extra: dict | None = None) -> dict:
        raw     = to_float(self.e_importo.get())
        importo = prezzo * raw / 100 if self.mutuo_mode.get() == "% Prezzo" else raw
        pct     = raw if self.mutuo_mode.get() == "% Prezzo" else (
            raw / prezzo * 100 if prezzo else 0
        )
        tasso_ann  = to_float(self.e_tasso.get()) / 100
        durata_ann = to_float(self.e_durata.get())

        r = tasso_ann / 12
        n = durata_ann * 12
        rata_base = importo * r / (1 - (1 + r) ** (-n)) if r > 0 and n > 0 else 0.0

        pol_si_imp  = to_float(self.e_pol_si.get())
        pol_v_imp   = to_float(self.e_pol_v.get())
        pol_si_mode = self.pol_si_mode.get()
        pol_v_mode  = self.pol_v_mode.get()

        pol_si_mens, _, pol_si_tot, pol_si_unica = _pol_breakdown(pol_si_imp, pol_si_mode, n)
        pol_v_mens,  _, pol_v_tot,  pol_v_unica  = _pol_breakdown(pol_v_imp,  pol_v_mode,  n)

        # Spese bancarie
        istruttoria = to_float(self.e_istruttoria.get())
        perizia     = to_float(self.e_perizia.get())
        imp_sost_mode = self.imp_sost_mode.get()
        if imp_sost_mode == "Prima casa":
            imp_sost = importo * 0.0025
        elif imp_sost_mode == "Seconda casa":
            imp_sost = importo * 0.02
        else:
            imp_sost = to_float(self.e_imp_sost.get())

        rata           = rata_base + pol_si_mens + pol_v_mens
        tot_restituito = rata_base * n
        tot_interessi  = tot_restituito - importo
        acconto        = prezzo - importo
        tot_costi_iniz = (acconto + notaio + agenzia + imposta
                          + pol_si_unica + pol_v_unica
                          + istruttoria + perizia + imp_sost)
        costo_totale   = (tot_restituito + tot_interessi
                          + pol_si_tot + pol_v_tot
                          + notaio + agenzia + imposta
                          + istruttoria + perizia + imp_sost)

        # TAEG — costi upfront inclusi: istruttoria, perizia, imp.sost., pol.unica scoppio
        taeg = calcola_taeg(
            importo,
            upfront_costs=istruttoria + perizia + imp_sost + pol_si_unica,
            rata_base=rata_base,
            n=int(n),
            pol_si_imp=pol_si_imp,
            pol_si_mode=pol_si_mode,
        )

        return {
            "label":          self._entry_nome.get() or f"Scenario {self._index + 1}",
            "prezzo":         prezzo,
            "importo":        importo,
            "pct_mutuo":      pct,
            "tasso_ann":      tasso_ann * 100,
            "durata_ann":     durata_ann,
            "rata_base":      rata_base,
            "rata":           rata,
            "tot_restituito": tot_restituito,
            "tot_interessi":  tot_interessi,
            "acconto":        acconto,
            "notaio":         notaio,
            "agenzia":        agenzia,
            "agenzia_tot":    agenzia,
            **(agenzia_extra or {}),
            "imposta":        imposta,
            "pol_si_imp":     pol_si_imp,  "pol_si_mode":  pol_si_mode,
            "pol_si_mens":    pol_si_mens, "pol_si_tot":   pol_si_tot,
            "pol_si_unica":   pol_si_unica,
            "pol_v_imp":      pol_v_imp,   "pol_v_mode":   pol_v_mode,
            "pol_v_mens":     pol_v_mens,  "pol_v_tot":    pol_v_tot,
            "pol_v_unica":    pol_v_unica,
            "istruttoria":    istruttoria,
            "perizia":        perizia,
            "imp_sost":       imp_sost,
            "imp_sost_mode":  imp_sost_mode,
            "taeg":           taeg,
            "tot_costi_iniz": tot_costi_iniz,
            "costo_totale":   costo_totale,
        }


# ── App principale ─────────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Calcoli Acquisto Immobile")
        self.resizable(False, False)

        self._scenari: list[MutuoWidget] = []

        outer = ctk.CTkScrollableFrame(self, width=700, height=940)
        outer.pack(padx=20, pady=20, fill="both", expand=True)

        # Rotella del mouse su Linux (Button-4/5) e Windows/Mac (MouseWheel)
        def _scroll(e):
            if e.num == 4 or e.delta > 0:
                outer._parent_canvas.yview_scroll(-1, "units")
            elif e.num == 5 or e.delta < 0:
                outer._parent_canvas.yview_scroll(1, "units")
        self.bind_all("<Button-4>", _scroll)
        self.bind_all("<Button-5>", _scroll)
        self.bind_all("<MouseWheel>", _scroll)

        # ── Sezione: Dati Immobile ─────────────────────────────────────────
        fi = ctk.CTkFrame(outer)
        fi.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(fi, text="Dati Immobile",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 4))
        ctk.CTkFrame(fi, height=2, fg_color=("gray70", "gray40")).pack(
            fill="x", padx=16, pady=(0, 10))
        gi = ctk.CTkFrame(fi, fg_color="transparent")
        gi.pack(padx=16, pady=(0, 12), fill="x")
        _lbl(gi, "Prezzo acquisto (€):", 0)
        self.e_prezzo = _entry(gi, 0, 1, "300000", width=160)

        # ── Sezione: Scenari Mutuo ─────────────────────────────────────────
        fs = ctk.CTkFrame(outer)
        fs.pack(fill="x", pady=(0, 10))
        hdr = ctk.CTkFrame(fs, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(hdr, text="Scenari Mutuo",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkButton(
            hdr, text="＋ Aggiungi scenario", width=160, height=28,
            font=ctk.CTkFont(size=12),
            command=self._aggiungi_scenario,
        ).pack(side="right")
        ctk.CTkFrame(fs, height=2, fg_color=("gray70", "gray40")).pack(
            fill="x", padx=16, pady=(0, 10))
        self._scenari_container = ctk.CTkFrame(fs, fg_color="transparent")
        self._scenari_container.pack(padx=16, pady=(0, 12), fill="x")

        # Primo scenario di default
        self._aggiungi_scenario()

        # ── Sezione: Costi Iniziali ────────────────────────────────────────
        fc = ctk.CTkFrame(outer)
        fc.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(fc, text="Costi Iniziali",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 4))
        ctk.CTkFrame(fc, height=2, fg_color=("gray70", "gray40")).pack(
            fill="x", padx=16, pady=(0, 10))
        gc = ctk.CTkFrame(fc, fg_color="transparent")
        gc.pack(padx=16, pady=(0, 12), fill="x")

        self.e_notaio  = self._lbl_entry(gc, "Notaio (€)",               0, "3000")

        # Agenzia immobiliare — modalità €/% con IVA
        ctk.CTkLabel(gc, text="Agenzia immobiliare:", anchor="w").grid(
            row=1, column=0, padx=(0, 12), pady=4, sticky="w")
        self.agenzia_mode = ctk.StringVar(value="% Prezzo")
        ctk.CTkSegmentedButton(
            gc, values=["€ Importo", "% Prezzo"],
            variable=self.agenzia_mode,
            command=self._on_agenzia_mode_change,
            width=200,
        ).grid(row=1, column=1, pady=4, sticky="w")
        self.e_agenzia = ctk.CTkEntry(gc, width=70)
        self.e_agenzia.insert(0, "4")
        self.e_agenzia.grid(row=1, column=2, padx=(8, 0), pady=4, sticky="w")
        self._lbl_agenzia_unit = ctk.CTkLabel(gc, text="%", anchor="w",
                                              text_color=("gray40", "gray60"))
        self._lbl_agenzia_unit.grid(row=1, column=3, padx=(4, 8), pady=4, sticky="w")
        ctk.CTkLabel(gc, text="+ IVA", anchor="w").grid(
            row=1, column=4, padx=(0, 4), pady=4, sticky="w")
        self.e_agenzia_iva = ctk.CTkEntry(gc, width=55)
        self.e_agenzia_iva.insert(0, "22")
        self.e_agenzia_iva.grid(row=1, column=5, pady=4, sticky="w")
        ctk.CTkLabel(gc, text="%", anchor="w",
                     text_color=("gray40", "gray60")).grid(
            row=1, column=6, padx=(4, 0), pady=4, sticky="w")

        # ── Imposta di registro (acquisto da privato) ────────────────────────
        ctk.CTkLabel(gc, text="Imposta di registro:", anchor="w").grid(
            row=2, column=0, padx=(0, 12), pady=4, sticky="w")
        self.imposta_tipo = ctk.StringVar(value="Prima casa")
        ctk.CTkSegmentedButton(
            gc, values=["Prima casa", "Seconda casa"],
            variable=self.imposta_tipo,
            width=220,
        ).grid(row=2, column=1, columnspan=2, pady=4, sticky="w")
        ctk.CTkLabel(gc, text="Valore catastale (€):", anchor="w").grid(
            row=3, column=0, padx=(0, 12), pady=4, sticky="w")
        self.e_val_catastale = ctk.CTkEntry(gc, width=160)
        self.e_val_catastale.insert(0, "0")
        self.e_val_catastale.grid(row=3, column=1, pady=4, sticky="w")

        # ── Bottoni ────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(outer, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame, text="Calcola Riepilogo",
            command=self.mostra_riepilogo,
        ).grid(row=0, column=0, padx=8)

        ctk.CTkButton(
            btn_frame, text="Genera PDF",
            command=self.genera_pdf,
            fg_color="#2a7a2a", hover_color="#215f21",
        ).grid(row=0, column=1, padx=8)

        # ── Riepilogo inline ───────────────────────────────────────────────
        self.riepilogo_box = ctk.CTkTextbox(
            outer, height=300, state="disabled",
            font=ctk.CTkFont(family="Courier", size=11),
        )
        self.riepilogo_box.pack(fill="x", pady=(10, 0))

    # ── Conversione modalità agenzia ─────────────────────────────────────
    def _on_agenzia_mode_change(self, value: str):
        prezzo  = to_float(self.e_prezzo.get())
        current = to_float(self.e_agenzia.get())
        iva     = to_float(self.e_agenzia_iva.get())
        self.e_agenzia.delete(0, "end")
        if value == "€ Importo":
            self._lbl_agenzia_unit.configure(text="€")
            self.e_agenzia_iva.configure(state="disabled")
            # Converte % → € lordo IVA
            eur = round(prezzo * current / 100 * (1 + iva / 100), 2) if prezzo else 0
            self.e_agenzia.insert(0, str(eur))
        else:
            self._lbl_agenzia_unit.configure(text="%")
            self.e_agenzia_iva.configure(state="normal")
            # Converte € lordo → % (al netto IVA)
            if prezzo > 0 and current > 0:
                divisore = 1 + iva / 100 if iva else 1
                pct = round(current / prezzo * 100 / divisore, 2)
            else:
                pct = 4.0
            self.e_agenzia.insert(0, str(pct))

    def _get_agenzia(self) -> tuple[float, float, float]:
        """Restituisce (totale_lordo, imponibile, iva_importo)."""
        prezzo = to_float(self.e_prezzo.get())
        val    = to_float(self.e_agenzia.get())
        iva    = to_float(self.e_agenzia_iva.get())
        if self.agenzia_mode.get() == "% Prezzo":
            imponibile = prezzo * val / 100
            iva_imp    = imponibile * iva / 100
            totale     = imponibile + iva_imp
        else:  # € Importo già lordo
            totale     = val
            iva_imp    = 0.0
            imponibile = val
        return totale, imponibile, iva_imp

    def _get_imposta(self) -> dict:
        """Imposte acquisto da privato: registro + ipotecaria (€50) + catastale (€50)."""
        val_cat = to_float(self.e_val_catastale.get())
        tipo    = self.imposta_tipo.get()
        pct     = 0.02 if tipo == "Prima casa" else 0.09
        registro   = round(val_cat * pct, 2)
        ipotecaria = 50.0
        catastale  = 50.0
        return {
            "tipo":          tipo,
            "pct":           pct,
            "val_catastale": val_cat,
            "registro":      registro,
            "ipotecaria":    ipotecaria,
            "catastale":     catastale,
            "totale":        registro + ipotecaria + catastale,
        }

    # ── Helpers UI ─────────────────────────────────────────────────────────
    @staticmethod
    def _lbl_entry(parent, label, row, default, width=160):
        ctk.CTkLabel(parent, text=label, anchor="w").grid(
            row=row, column=0, padx=(0, 12), pady=4, sticky="w")
        e = ctk.CTkEntry(parent, width=width)
        e.insert(0, default)
        e.grid(row=row, column=1, pady=4, sticky="w")
        return e

    # ── Gestione scenari ───────────────────────────────────────────────────
    def _aggiungi_scenario(self):
        idx = len(self._scenari)
        defaults = self._scenari[-1].get_values() if self._scenari else None
        w = MutuoWidget(
            self._scenari_container,
            index=idx,
            on_remove=self._rimuovi_scenario,
            get_prezzo=lambda: to_float(self.e_prezzo.get()),
            defaults=defaults,
        )
        w.pack(fill="x", pady=(0, 8))
        self._scenari.append(w)

    def _rimuovi_scenario(self, widget: MutuoWidget):
        if len(self._scenari) == 1:
            messagebox.showwarning("Attenzione",
                                   "Deve esserci almeno uno scenario.")
            return
        self._scenari.remove(widget)
        widget.destroy()
        for i, s in enumerate(self._scenari):
            s.set_index(i)

    # ── Calcola tutti gli scenari ──────────────────────────────────────────
    def _calcola_tutti(self) -> list:
        prezzo  = to_float(self.e_prezzo.get())
        notaio  = to_float(self.e_notaio.get())
        agenzia_tot, agenzia_impon, agenzia_iva = self._get_agenzia()
        agenzia_pct   = to_float(self.e_agenzia.get()) if self.agenzia_mode.get() == "% Prezzo" else 0
        agenzia_iva_pct = to_float(self.e_agenzia_iva.get())
        imp_dict = self._get_imposta()
        imposta  = imp_dict["totale"]
        extra = {
            "agenzia_tot":     agenzia_tot,
            "agenzia_impon":   agenzia_impon,
            "agenzia_iva":     agenzia_iva,
            "agenzia_pct":     agenzia_pct,
            "agenzia_iva_pct": agenzia_iva_pct,
            "agenzia_mode":    self.agenzia_mode.get(),
            "imp_tipo":        imp_dict["tipo"],
            "imp_pct":         imp_dict["pct"],
            "imp_registro":    imp_dict["registro"],
            "imp_ipotecaria":  imp_dict["ipotecaria"],
            "imp_catastale":   imp_dict["catastale"],
        }
        return [s.calcola(prezzo, notaio, agenzia_tot, imposta, extra)
                for s in self._scenari]

    # ── Riepilogo testuale ─────────────────────────────────────────────────
    def mostra_riepilogo(self):
        scenari = self._calcola_tutti()
        lines = [
            "═══════════════════════════════════════════════════",
            "  RIEPILOGO COSTI ACQUISTO IMMOBILE",
            "═══════════════════════════════════════════════════",
        ]
        for d in scenari:
            lines += [
                "",
                f"── {d['label']}  ({d['pct_mutuo']:.1f}%"
                f" · {fmt_eur(d['importo'])}) ──",
                f"  Tasso annuo (TAN):    {d['tasso_ann']:.2f} %"
                f"  –  {int(d['durata_ann'])} anni",
                f"  TAEG:                 "
                + (f"{d['taeg']:.2f} %" if d.get('taeg') is not None else "n.d."),
                f"  Rata mutuo:           {fmt_eur(d['rata_base'])}",
                f"  + Pol. scoppio/inc.:  "
                f"{_pol_line(d['pol_si_imp'], d['pol_si_mode'], d['pol_si_mens'])}",
                f"  + Pol. vita:          "
                f"{_pol_line(d['pol_v_imp'], d['pol_v_mode'], d['pol_v_mens'])}",
                f"  Rata totale:          {fmt_eur(d['rata'])}",
                f"  Interessi totali:     {fmt_eur(d['tot_interessi'])}",
                f"  Totale restituito:    {fmt_eur(d['tot_restituito'])}",
                "  ───────────────────────────────────────────────",
                f"  Acconto:              {fmt_eur(d['acconto'])}",
                f"  Notaio:               {fmt_eur(d['notaio'])}",
                f"  Agenzia:              {fmt_eur(d['agenzia_tot'])}"
                + (f"  ({d['agenzia_pct']:.2f}% + IVA {d['agenzia_iva_pct']:.0f}%)"
                   if d.get('agenzia_mode') == '% Prezzo' else ""),
                f"  Imp. di registro:     {fmt_eur(d.get('imp_registro', 0))}"
                f"  ({d.get('imp_tipo','')}, {d.get('imp_pct', 0)*100:.1f}% v.c.)",
                f"  Imp. ipotecaria:      {fmt_eur(d.get('imp_ipotecaria', 50))}  (fissa)",
                f"  Imp. catastale:       {fmt_eur(d.get('imp_catastale', 50))}  (fissa)",
                f"  Spese istruttoria:    {fmt_eur(d['istruttoria'])}",
                f"  Spese perizia:        {fmt_eur(d['perizia'])}",
                f"  Imposta sostitutiva:  {fmt_eur(d['imp_sost'])}"
                f"  [{d['imp_sost_mode']}]",
                *([f"  Pol. scoppio/inc.:    "
                   f"{fmt_eur(d['pol_si_unica'])} (unica)"]
                  if d["pol_si_unica"] > 0 else []),
                *([f"  Pol. vita:            "
                   f"{fmt_eur(d['pol_v_unica'])} (unica)"]
                  if d["pol_v_unica"] > 0 else []),
                f"  Tot. costi iniziali:  {fmt_eur(d['tot_costi_iniz'])}",
                f"  ► COSTO TOTALE:       {fmt_eur(d['costo_totale'])}",
            ]
        lines.append("")
        lines.append("═══════════════════════════════════════════════════")

        text = "\n".join(lines)
        self.riepilogo_box.configure(state="normal")
        self.riepilogo_box.delete("1.0", "end")
        self.riepilogo_box.insert("end", text)
        self.riepilogo_box.configure(state="disabled")

    # ── Genera PDF ─────────────────────────────────────────────────────────
    def genera_pdf(self):
        scenari = self._calcola_tutti()
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"riepilogo_immobile_{datetime.now():%Y%m%d}.pdf",
        )
        if not path:
            return

        doc = SimpleDocTemplate(
            path, pagesize=A4,
            leftMargin=2.5 * cm, rightMargin=2.5 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "title", parent=styles["Heading1"],
            fontSize=16, spaceAfter=6, alignment=TA_CENTER,
        )
        sub_style = ParagraphStyle(
            "sub", parent=styles["Normal"],
            fontSize=9, textColor=colors.gray,
        )
        total_style = ParagraphStyle(
            "total", parent=styles["Normal"],
            fontSize=12, spaceAfter=4, alignment=TA_CENTER,
        )

        base_tbl = TableStyle([
            ("FONTNAME",  (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",  (0, 0), (-1, 0), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#eaf2f8")]),
            ("FONTSIZE",  (0, 1), (-1, -1), 10),
            ("ALIGN",     (1, 0), (1, -1), "RIGHT"),
            ("GRID",      (0, 0), (-1, -1), 0.4, colors.HexColor("#aab7b8")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
        col_w = [11 * cm, 5 * cm]

        story = []
        story.append(Paragraph("Riepilogo Costi Acquisto Immobile", title_style))
        story.append(Paragraph(
            f"Generato il {datetime.now():%d/%m/%Y}", sub_style))
        story.append(Spacer(1, 0.4 * cm))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#1a5276")))

        for i, d in enumerate(scenari):
            hex_color = SCENARIO_COLORS[i % len(SCENARIO_COLORS)]
            scen_color = colors.HexColor(hex_color)
            hdr_style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), scen_color),
                ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ])
            bold_last = TableStyle([
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ])
            tbl_s  = TableStyle(base_tbl.getCommands() + hdr_style.getCommands())
            tbl_s2 = TableStyle(base_tbl.getCommands() + hdr_style.getCommands()
                                + bold_last.getCommands())

            story.append(Spacer(1, 0.5 * cm))
            sec_style = ParagraphStyle(
                f"sh{i}", parent=styles["Heading2"],
                fontSize=13, spaceBefore=10, spaceAfter=4,
                textColor=scen_color,
            )
            story.append(Paragraph(
                f"{d['label']} — {fmt_eur(d['importo'])}"
                f" ({d['pct_mutuo']:.1f}% del prezzo · {int(d['durata_ann'])} anni)",
                sec_style,
            ))

            mutuo_data = [
                ["Voce", "Importo"],
                [f"Importo mutuo ({d['pct_mutuo']:.1f}% del prezzo)",
                 fmt_eur(d["importo"])],
                ["Tasso annuo (TAN)", f"{d['tasso_ann']:.2f} %"],
                ["TAEG", f"{d['taeg']:.2f} %" if d.get('taeg') is not None else "n.d."],
                ["Durata", f"{int(d['durata_ann'])} anni"],
                ["Rata mutuo (cap. + int.)", fmt_eur(d["rata_base"])],
                [f"  + Pol. scoppio/incendio [{d['pol_si_mode']}]",
                 _pol_line(d["pol_si_imp"], d["pol_si_mode"], d["pol_si_mens"])],
                [f"  + Polizza vita [{d['pol_v_mode']}]",
                 _pol_line(d["pol_v_imp"], d["pol_v_mode"], d["pol_v_mens"])],
                ["Rata totale mensile", fmt_eur(d["rata"])],
                ["Interessi totali", fmt_eur(d["tot_interessi"])],
                ["Totale restituito", fmt_eur(d["tot_restituito"])],
                ["Totale polizze (intera durata)",
                 fmt_eur(d["pol_si_tot"] + d["pol_v_tot"])],
            ]
            t = Table(mutuo_data, colWidths=col_w)
            t.setStyle(tbl_s)
            story.append(t)
            story.append(Spacer(1, 0.3 * cm))

            costi_data = [
                ["Voce", "Importo"],
                ["Acconto (prezzo − mutuo)", fmt_eur(d["acconto"])],
                ["Notaio", fmt_eur(d["notaio"])],
                ["Agenzia immobiliare",
                 (f"{fmt_eur(d.get('agenzia_impon', d['agenzia']))} + IVA {d.get('agenzia_iva_pct',0):.0f}%"
                  f" = {fmt_eur(d['agenzia_tot'])}"
                  if d.get('agenzia_mode') == '% Prezzo'
                  else fmt_eur(d['agenzia_tot']))],
                [f"Imposta di registro ({d.get('imp_tipo','')}, {d.get('imp_pct',0)*100:.1f}% v.c.)",
                 fmt_eur(d.get('imp_registro', 0))],
                ["Imposta ipotecaria (fissa)", fmt_eur(d.get('imp_ipotecaria', 50))],
                ["Imposta catastale (fissa)",  fmt_eur(d.get('imp_catastale',  50))],
                ["Spese istruttoria", fmt_eur(d["istruttoria"])],
                ["Spese perizia", fmt_eur(d["perizia"])],
                [f"Imposta sostitutiva [{d['imp_sost_mode']}]",
                 fmt_eur(d["imp_sost"])],
            ]
            if d["pol_si_unica"] > 0:
                costi_data.append(["Pol. scoppio/incendio (unica)",
                                   fmt_eur(d["pol_si_unica"])])
            if d["pol_v_unica"] > 0:
                costi_data.append(["Polizza vita (unica)",
                                   fmt_eur(d["pol_v_unica"])])
            costi_data.append(["TOTALE costi iniziali",
                                fmt_eur(d["tot_costi_iniz"])]) 

            t2 = Table(costi_data, colWidths=col_w)
            t2.setStyle(tbl_s2)
            story.append(t2)
            story.append(Spacer(1, 0.3 * cm))

            story.append(HRFlowable(width="100%", thickness=0.8,
                                    color=scen_color))
            ts = ParagraphStyle(
                f"tot{i}", parent=total_style,
                textColor=scen_color,
            )
            story.append(Paragraph(
                f"<b>COSTO TOTALE {d['label'].upper()}:"
                f"  {fmt_eur(d['costo_totale'])}</b>",
                ts,
            ))

        doc.build(story)
        messagebox.showinfo("PDF generato", f"File salvato in:\n{path}")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
