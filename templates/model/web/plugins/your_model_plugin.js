/**
 * Frontend plugin stub (copy to web/plugins/<id>_plugin.js).
 * Register the import in web/dashboard_adapter.js.
 * See templates/model/ and docs/ADDING_A_MODEL.md § Quick checklist.
 */
import { createPlugin } from "../model_plugin.js";

export default createPlugin({
  id: "your_model",
  presentation: {
    choroplethField: "your_model_mean",
    primaryMetricKeys: ["your_model_mean", "tract_mean_your_model"],
    runVerb: "Your Model",
    runProgressStart: "Starting analysis on the server…",
    runProgressWorking: "Still working — large scenes can take several minutes.",
    barChartLabelProject: "Mean value",
    barChartHeadingProject: "Mean value by city",
    analysisLayerLabel: "Your model",
    legendLabel: "Your model",
    metricUnit: "",
    chatContextSummary:
      "Results for {city}. Per-tract column: your_model_mean. " +
      "Combine with median_income_usd and population for equity questions.",
    cardTitle: "Run analysis for a city",
    portfolioHint: "Upload input GeoTIFFs per city for the selected model.",
    tractDetailLabel: "Mean value",
    chatAnalysisLabel: "your model output",
  },
});
