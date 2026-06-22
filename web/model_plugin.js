/**
 * Model plugin contract — each analysis model owns presentation + rendering hooks.
 *
 * @typedef {object} ModelPlugin
 * @property {string} id
 * @property {object} presentation
 * @property {(city: object, layerId: string, appMode: string, analysisLayerId: string) => string|null} choroplethField
 * @property {(city: object, runStats: object) => string} renderStats
 * @property {(ctx: LegendContext) => LegendResult|null} renderLegend
 * @property {(ctx: ScaleContext) => boolean} showsScaleControls
 * @property {(field: string, valueRange: object|null, ctx: PaintContext) => object|null} choroplethFillPaint
 * @property {(value: *, field: string) => string} formatChoroplethValue
 * @property {(field: string) => boolean} usesLocalValueScale
 * @property {(city: object, runStats: object) => string} chatContext
 * @property {(city: object) => string} chatContextSummary
 * @property {(ctx: KeyQueryContext) => Array<{label: string, prompt: string, style?: string}>|null} keyQueries
 * @property {(props: object, field: string, layerLabel: string) => string} tractPopupMetric
 * @property {(props: object) => [string, string]|null} tractDetailRow
 */

/**
 * @param {Partial<ModelPlugin> & { id: string, presentation?: object }} def
 * @returns {ModelPlugin}
 */
export function createPlugin(def) {
  const presentation = def.presentation || {};

  return {
    id: def.id,
    presentation,

    choroplethField(city, layerId, appMode, analysisLayerId) {
      if (def.choroplethField) {
        return def.choroplethField(city, layerId, appMode, analysisLayerId);
      }
      const field = presentation.choroplethField;
      if (layerId !== (analysisLayerId || "analysis")) return null;
      if (appMode === "project" && city?.status === "ready" && field) return field;
      return null;
    },

    renderStats(city, runStats) {
      if (def.renderStats) return def.renderStats(city, runStats);
      return "";
    },

    renderLegend(ctx) {
      if (def.renderLegend) return def.renderLegend(ctx);
      return null;
    },

    showsScaleControls(ctx) {
      if (def.showsScaleControls) return def.showsScaleControls(ctx);
      return false;
    },

    choroplethFillPaint(field, valueRange, ctx) {
      if (def.choroplethFillPaint) return def.choroplethFillPaint(field, valueRange, ctx);
      return null;
    },

    formatChoroplethValue(value, field) {
      if (def.formatChoroplethValue) return def.formatChoroplethValue(value, field);
      if (value == null || value === "") return "—";
      const unit = presentation.metricUnit || "";
      return unit ? `${value}${unit}` : String(value);
    },

    usesLocalValueScale(field) {
      if (def.usesLocalValueScale) return def.usesLocalValueScale(field);
      return false;
    },

    chatContext(city, runStats) {
      if (def.chatContext) return def.chatContext(city, runStats);
      return "";
    },

    chatContextSummary(city) {
      if (def.chatContextSummary) return def.chatContextSummary(city);
      const template = presentation.chatContextSummary || "";
      return template.replace("{city}", city?.name || "this city");
    },

    keyQueries(ctx) {
      if (def.keyQueries) return def.keyQueries(ctx);
      return null;
    },

    tractPopupMetric(props, field, layerLabel) {
      if (def.tractPopupMetric) return def.tractPopupMetric(props, field, layerLabel);
      if (field && props[field] != null) {
        const display = def.formatChoroplethValue
          ? def.formatChoroplethValue(props[field], field)
          : String(props[field]);
        return `<div class="gf-tract-popup-metric">${display}</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
      }
      return "";
    },

    tractDetailRow(props) {
      if (def.tractDetailRow) return def.tractDetailRow(props);
      const field = presentation.choroplethField;
      if (field && props[field] != null) {
        const label = presentation.tractDetailLabel || presentation.legendLabel || "Metric";
        const value = def.formatChoroplethValue
          ? def.formatChoroplethValue(props[field], field)
          : String(props[field]);
        return [label, value];
      }
      return null;
    },
  };
}
