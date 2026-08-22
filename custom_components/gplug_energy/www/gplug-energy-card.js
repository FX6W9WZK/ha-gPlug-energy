/**
 * gPlug Energy Card – Custom Lovelace Card
 * Auto-registered by the gPlug Energy integration.
 *
 * Shows real-time power flow, energy totals, and per-phase details.
 * Supports: DE, EN, FR, IT (fallback: EN)
 */

const CARD_VERSION = "1.2.3";

const TRANSLATIONS = {
  en: {
    import: "Import", export: "Export", export_label: "Export",
    ht: "HT", nt: "NT", phases: "Phases",
    tariff1: "Tariff 1 (HT)", tariff2: "Tariff 2 (NT)",
    title_default: "gPlug Smart Meter",
    show_phases: "Show phase details", show_export: "Show export/feed-in",
    entity_prefix_label: "Entity prefix (e.g. sensor.gplugd_)",
  },
  de: {
    import: "Bezug", export: "Einspeisung", export_label: "Einspeisung",
    ht: "HT", nt: "NT", phases: "Phasen",
    tariff1: "Tarif 1 (HT)", tariff2: "Tarif 2 (NT)",
    title_default: "gPlug Smart Meter",
    show_phases: "Phasendetails anzeigen", show_export: "Einspeisung anzeigen",
    entity_prefix_label: "Entitäts-Präfix (z.B. sensor.gplugd_)",
  },
  fr: {
    import: "Consommation", export: "Injection", export_label: "Injection",
    ht: "HP", nt: "HC", phases: "Phases",
    tariff1: "Tarif 1 (HP)", tariff2: "Tarif 2 (HC)",
    title_default: "gPlug Smart Meter",
    show_phases: "Afficher les phases", show_export: "Afficher l'injection",
    entity_prefix_label: "Préfixe d'entité (ex. sensor.gplugd_)",
  },
  it: {
    import: "Consumo", export: "Immissione", export_label: "Immissione",
    ht: "alta", nt: "bassa", phases: "Fasi",
    tariff1: "Tariffa 1 (alta)", tariff2: "Tariffa 2 (bassa)",
    title_default: "gPlug Smart Meter",
    show_phases: "Mostra dettagli fase", show_export: "Mostra immissione",
    entity_prefix_label: "Prefisso entità (es. sensor.gplugd_)",
  },
};

function _t(hass, key) {
  const lang = (hass?.language || "en").substring(0, 2);
  return (TRANSLATIONS[lang] || TRANSLATIONS.en)[key] || TRANSLATIONS.en[key] || key;
}

class GPlugEnergyCard extends HTMLElement {
  static get properties() {
    return { hass: {}, config: {} };
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    if (!config.entry_id && !config.entity_prefix) {
      throw new Error("Please define entry_id or entity_prefix");
    }
    this._config = {
      title: config.title || "",
      entity_prefix: config.entity_prefix || "",
      entry_id: config.entry_id || "",
      show_phases: config.show_phases !== false,
      show_export: config.show_export !== false,
      ...config,
    };
    this._render();
  }

  getCardSize() {
    return this._config?.show_phases ? 6 : 4;
  }

  static getConfigElement() {
    return document.createElement("gplug-energy-card-editor");
  }

  static getStubConfig() {
    return {
      title: "",
      entity_prefix: "sensor.gplugd_",
      show_phases: true,
      show_export: true,
    };
  }

  _getState(suffix) {
    if (!this._hass) return null;
    const prefix = this._config.entity_prefix;
    const entityId = prefix + suffix;
    return this._hass.states[entityId] || null;
  }

  _val(suffix, decimals = 1) {
    const s = this._getState(suffix);
    if (!s || isNaN(parseFloat(s.state))) return "\u2014";
    return parseFloat(s.state).toFixed(decimals);
  }

  _render() {
    if (!this._hass || !this._config) return;

    const t = (key) => _t(this._hass, key);
    const title = this._config.title || t("title_default");

    const Pi = parseFloat(this._val("power_import", 3)) || 0;
    const Po = parseFloat(this._val("power_export", 3)) || 0;
    const netPower = Pi - Po;
    const isExporting = netPower < -0.001;
    const flowColor = isExporting ? "#1D9E75" : "#D85A30";
    const flowLabel = isExporting ? t("export") : t("import");
    const absNet = Math.abs(netPower).toFixed(3);

    const dark = document.documentElement.getAttribute("data-theme") === "dark"
      || window.matchMedia("(prefers-color-scheme: dark)").matches;

    const text1 = "var(--primary-text-color, #333)";
    const text2 = "var(--secondary-text-color, #888)";
    const border = "var(--divider-color, rgba(0,0,0,0.12))";

    let phasesHTML = "";
    if (this._config.show_phases) {
      const phases = [1, 2, 3].map(n => {
        const v = this._val(`voltage_l${n}`, 1);
        const a = this._val(`current_l${n}`, 1);
        const pi = this._val(`power_import_l${n}`, 0);
        return `
          <div style="text-align:center;flex:1;padding:4px 0">
            <div style="font-size:11px;color:${text2};margin-bottom:2px">L${n}</div>
            <div style="font-size:14px;font-weight:500;color:${text1}">${v} V</div>
            <div style="font-size:12px;color:${text2}">${a} A \u00b7 ${pi} W</div>
          </div>
        `;
      }).join(`<div style="width:1px;background:${border};margin:4px 0"></div>`);

      phasesHTML = `
        <div style="display:flex;padding:8px 16px 12px;border-top:1px solid ${border}">
          ${phases}
        </div>
      `;
    }

    let exportHTML = "";
    if (this._config.show_export) {
      exportHTML = `
        <div style="display:flex;justify-content:space-between;padding:4px 16px;font-size:12px;color:${text2}">
          <span>${t("export_label")}: ${this._val("energy_export_tariff_1", 3)} kWh</span>
          <span>Po: ${this._val("power_export", 3)} kW</span>
        </div>
      `;
    }

    this.innerHTML = `
      <ha-card>
        <div style="padding:16px 16px 8px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div style="font-size:16px;font-weight:500;color:${text1}">${title}</div>
            <div style="font-size:11px;color:${text2}">gPlug Energy</div>
          </div>

          <div style="text-align:center;padding:12px 0">
            <div style="font-size:12px;color:${text2};margin-bottom:4px">${flowLabel}</div>
            <div style="font-size:32px;font-weight:600;color:${flowColor};line-height:1.1">${absNet}</div>
            <div style="font-size:14px;color:${text2}">kW</div>
          </div>

          <div style="display:flex;gap:8px;padding:8px 0 4px">
            <div style="flex:1;background:${dark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)'};border-radius:8px;padding:10px 12px">
              <div style="font-size:11px;color:${text2}">${t("import")} ${t("ht")} (Ei1)</div>
              <div style="font-size:16px;font-weight:500;color:${text1}">${this._val("energy_import_tariff_1", 1)} <span style="font-size:12px;font-weight:400">kWh</span></div>
            </div>
            <div style="flex:1;background:${dark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)'};border-radius:8px;padding:10px 12px">
              <div style="font-size:11px;color:${text2}">${t("import")} ${t("nt")} (Ei2)</div>
              <div style="font-size:16px;font-weight:500;color:${text1}">${this._val("energy_import_tariff_2", 1)} <span style="font-size:12px;font-weight:400">kWh</span></div>
            </div>
          </div>

          ${exportHTML}
        </div>

        ${phasesHTML}
      </ha-card>
    `;
  }
}

class GPlugEnergyCardEditor extends HTMLElement {
  set hass(hass) { this._hass = hass; this._render(); }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
    if (!this._config) return;
    const t = (key) => _t(this._hass, key);

    this.innerHTML = `
      <div style="padding:16px">
        <ha-textfield
          label="Title"
          id="title"
          value="${this._config.title || ""}"
          placeholder="${t("title_default")}"
        ></ha-textfield>
        <ha-textfield
          label="${t("entity_prefix_label")}"
          id="entity_prefix"
          value="${this._config.entity_prefix || "sensor.gplugd_"}"
          style="margin-top:8px"
        ></ha-textfield>
        <ha-formfield label="${t("show_phases")}" style="margin-top:8px;display:block">
          <ha-switch id="show_phases" ${this._config.show_phases !== false ? "checked" : ""}></ha-switch>
        </ha-formfield>
        <ha-formfield label="${t("show_export")}" style="margin-top:4px;display:block">
          <ha-switch id="show_export" ${this._config.show_export !== false ? "checked" : ""}></ha-switch>
        </ha-formfield>
      </div>
    `;

    this.querySelector("#title").addEventListener("change", (e) => {
      this._config = { ...this._config, title: e.target.value };
      this._fire();
    });
    this.querySelector("#entity_prefix").addEventListener("change", (e) => {
      this._config = { ...this._config, entity_prefix: e.target.value };
      this._fire();
    });
    this.querySelector("#show_phases").addEventListener("change", (e) => {
      this._config = { ...this._config, show_phases: e.target.checked };
      this._fire();
    });
    this.querySelector("#show_export").addEventListener("change", (e) => {
      this._config = { ...this._config, show_export: e.target.checked };
      this._fire();
    });
  }

  _fire() {
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: this._config } })
    );
  }
}

customElements.define("gplug-energy-card", GPlugEnergyCard);
customElements.define("gplug-energy-card-editor", GPlugEnergyCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "gplug-energy-card",
  name: "gPlug Energy",
  description: "Real-time smart meter overview with power flow, tariffs, and phase details.",
  preview: true,
  documentationURL: "https://github.com/FX6W9WZK/ha-gPlug-energy",
});

console.info(
  `%c gPlug Energy Card v${CARD_VERSION} `,
  "background:#1D9E75;color:#fff;font-weight:bold;padding:2px 6px;border-radius:4px"
);
