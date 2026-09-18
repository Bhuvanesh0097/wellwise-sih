import { useEffect, useState } from "react";
import {
  getDigitalTwin,
  getWells,
  getOptimization,
  getDecisionHistory,
  getTelemetryHistory,
  getSystemHealth,
  runWhatIf,
  submitEngineerDecision,
  type DigitalTwinResponse,
  type Well,
  type SystemHealth,
  type WhatIfResponse,
  type OptimizationResponse,
  type EngineerDecisionResponse,
  type DecisionHistoryResponse,
  type HistoricalTelemetry,
} from "./services/api";
import "./App.css";

type Scenario = {
  steam_rate: number;
  steam_temperature: number;
  injection_pressure: number;
  injection_duration: number;
  soak_time: number;
  stroke_length: number;
  spm: number;
  vfd_frequency: number;
};

type ActiveSection =
  | "dashboard"
  | "digital-twin"
  | "what-if"
  | "optimization"
  | "review"
  | "history";

type TrendKey =
  | "oil_rate"
  | "reservoir_temperature"
  | "reservoir_pressure"
  | "energy"
  | "spm"
  | "pump_fillage";

const sectionMeta: Record<
  ActiveSection,
  { title: string; subtitle: string }
> = {
  dashboard: {
    title: "Dashboard",
    subtitle: "Operational overview of the selected well",
  },
  "digital-twin": {
    title: "Digital Twin",
    subtitle: "Current state and 24-hour model predictions",
  },
  "what-if": {
    title: "What-If Simulation",
    subtitle: "Engineer-controlled scenario analysis",
  },
  optimization: {
    title: "Optimization",
    subtitle: "Model-based CSS and SRP operating point",
  },
  review: {
    title: "Engineer Review",
    subtitle: "Human approval workflow for AI recommendations",
  },
  history: {
    title: "Historical Trends",
    subtitle: "Telemetry trends and engineer audit history",
  },
};

const trendMeta: Record<
  TrendKey,
  { label: string; unit: string }
> = {
  oil_rate: { label: "Oil Rate", unit: "BOPD" },
  reservoir_temperature: {
    label: "Reservoir Temperature",
    unit: "°C",
  },
  reservoir_pressure: {
    label: "Reservoir Pressure",
    unit: "",
  },
  energy: { label: "Energy", unit: "" },
  spm: { label: "SPM", unit: "" },
  pump_fillage: {
    label: "Pump Fillage",
    unit: "%",
  },
};

const navItems: Array<[ActiveSection, string]> = [
  ["dashboard", "Dashboard"],
  ["digital-twin", "Digital Twin"],
  ["what-if", "What-If Simulation"],
  ["optimization", "Optimization"],
  ["review", "Engineer Review"],
  ["history", "Historical Trends"],
];

function formatDateTime(value: string) {
  return new Date(value).toLocaleString();
}

function signedPct(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatParameterName(key: string) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getTrendValue(
  row: HistoricalTelemetry,
  key: TrendKey
) {
  return row[key];
}

function TrendChart({
  data,
  metric,
}: {
  data: HistoricalTelemetry[];
  metric: TrendKey;
}) {
  const meta = trendMeta[metric];

  if (data.length < 2) {
    return (
      <div className="trend-empty">
        Not enough telemetry points for this trend.
      </div>
    );
  }

  const ordered = [...data].reverse();
  const values = ordered.map((row) =>
    getTrendValue(row, metric)
  );

  const width = 760;
  const height = 220;
  const padX = 24;
  const padY = 24;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values
    .map((value, index) => {
      const x =
        padX +
        (index / Math.max(values.length - 1, 1)) *
          (width - padX * 2);

      const y =
        height -
        padY -
        ((value - min) / range) *
          (height - padY * 2);

      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const first = values[0];
  const last = values[values.length - 1];

  return (
    <div className="trend-chart-wrap">
      <div className="trend-chart-summary">
        <div>
          <span>Latest</span>
          <strong>
            {last.toFixed(2)} {meta.unit}
          </strong>
        </div>

        <div>
          <span>Range</span>
          <strong>
            {min.toFixed(2)} — {max.toFixed(2)}
          </strong>
        </div>

        <div>
          <span>Change</span>
          <strong>
            {last - first >= 0 ? "+" : ""}
            {(last - first).toFixed(2)}
          </strong>
        </div>
      </div>

      <svg
        className="trend-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${meta.label} historical trend`}
      >
        <line
          x1={padX}
          y1={padY}
          x2={width - padX}
          y2={padY}
          className="trend-grid-line"
        />

        <line
          x1={padX}
          y1={height / 2}
          x2={width - padX}
          y2={height / 2}
          className="trend-grid-line"
        />

        <line
          x1={padX}
          y1={height - padY}
          x2={width - padX}
          y2={height - padY}
          className="trend-grid-line"
        />

        <polyline
          points={points}
          fill="none"
          className="trend-line"
        />
      </svg>

      <div className="trend-axis">
        <span>
          {formatDateTime(ordered[0].timestamp)}
        </span>

        <span>
          {formatDateTime(
            ordered[ordered.length - 1].timestamp
          )}
        </span>
      </div>
    </div>
  );
}

function App() {
  const [wells, setWells] = useState<Well[]>([]);
  const [selectedWell, setSelectedWell] = useState("");

  const [activeSection, setActiveSection] =
    useState<ActiveSection>("dashboard");

  const [data, setData] =
    useState<DigitalTwinResponse | null>(null);

  const [loadingWells, setLoadingWells] = useState(true);
  const [loadingTwin, setLoadingTwin] = useState(false);
  const [loadingOptimization, setLoadingOptimization] =
    useState(false);

  const [error, setError] = useState<string | null>(null);

  const [scenario, setScenario] = useState<Scenario>({
    steam_rate: 1.2,
    steam_temperature: 250,
    injection_pressure: 150,
    injection_duration: 14,
    soak_time: 48,
    stroke_length: 74,
    spm: 1,
    vfd_frequency: 33.33,
  });

  const [scenarioWellId, setScenarioWellId] =
    useState("");

  const [whatIfResult, setWhatIfResult] =
    useState<WhatIfResponse | null>(null);

  const [runningWhatIf, setRunningWhatIf] =
    useState(false);

  const [optimizationData, setOptimizationData] =
    useState<OptimizationResponse | null>(null);

  const [decisionResult, setDecisionResult] =
    useState<EngineerDecisionResponse | null>(null);

  const [decisionHistory, setDecisionHistory] =
    useState<DecisionHistoryResponse | null>(null);

  const [historyLoading, setHistoryLoading] =
    useState(false);

  const [decisionBusy, setDecisionBusy] =
    useState(false);

  const [showRejectBox, setShowRejectBox] =
    useState(false);

  const [rejectionReason, setRejectionReason] =
    useState("");

  const [historyRefreshKey, setHistoryRefreshKey] =
    useState(0);

  const [telemetryHistory, setTelemetryHistory] =
    useState<HistoricalTelemetry[]>([]);
  const [systemHealth, setSystemHealth] =
  useState<SystemHealth | null>(null);

const [systemHealthLoading, setSystemHealthLoading] =
  useState(false);

const [showSystemStatus, setShowSystemStatus] =
  useState(false);

  const [telemetryHistoryLoading, setTelemetryHistoryLoading] =
    useState(false);

  const [trendMetric, setTrendMetric] =
    useState<TrendKey>("oil_rate");

  // ----------------------------------------------------------
  // Load wells
  // ----------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function loadWells() {
      try {
        setLoadingWells(true);
        setError(null);

        const result = await getWells();

        if (cancelled) return;

        setWells(result);

        if (result.length > 0) {
          setSelectedWell(result[0].well_id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load wells"
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingWells(false);
        }
      }
    }

    loadWells();

    return () => {
      cancelled = true;
    };
  }, []);

  // ----------------------------------------------------------
  // Load Digital Twin
  // ----------------------------------------------------------

  useEffect(() => {
    if (!selectedWell) return;

    let cancelled = false;

    async function loadDigitalTwin() {
      try {
        setLoadingTwin(true);
        setError(null);

        const result = await getDigitalTwin(
          selectedWell
        );

        if (cancelled) return;

        setData(result);

        // Only initialize scenario values once per well.
        if (scenarioWellId !== selectedWell) {
          const recommendation =
            result.optimization?.recommendation;

          setScenario({
            steam_rate:
              recommendation?.steam_rate ?? 1.2,
            steam_temperature:
              recommendation?.steam_temperature ?? 250,
            injection_pressure:
              recommendation?.injection_pressure ?? 150,
            injection_duration:
              recommendation?.injection_duration ?? 14,
            soak_time:
              recommendation?.soak_time ?? 48,
            stroke_length:
              recommendation?.stroke_length ??
              result.telemetry.stroke_length ??
              74,
            spm:
              recommendation?.spm ??
              result.telemetry.spm ??
              1,
            vfd_frequency:
              recommendation?.vfd_frequency ??
              result.telemetry.vfd_frequency ??
              33.33,
          });

          setScenarioWellId(selectedWell);
          setWhatIfResult(null);
          setDecisionResult(null);
          setOptimizationData(null);
          setShowRejectBox(false);
          setRejectionReason("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load Digital Twin"
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingTwin(false);
        }
      }
    }

    loadDigitalTwin();

    const interval = window.setInterval(
      loadDigitalTwin,
      30000
    );

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [selectedWell, scenarioWellId]);

  // ----------------------------------------------------------
  // Load optimization when needed
  // ----------------------------------------------------------

  useEffect(() => {
    if (!selectedWell) return;

    const needsOptimization =
      activeSection === "optimization" ||
      activeSection === "review";

    if (!needsOptimization) return;

    let cancelled = false;

    async function loadOptimization() {
      try {
        setLoadingOptimization(true);
        setError(null);

        const result = await getOptimization(
          selectedWell
        );

        if (!cancelled) {
          setOptimizationData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setOptimizationData(null);
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load optimization"
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingOptimization(false);
        }
      }
    }

    loadOptimization();

    return () => {
      cancelled = true;
    };
  }, [selectedWell, activeSection]);

  // ----------------------------------------------------------
  // Load engineer decision history
  // ----------------------------------------------------------

  useEffect(() => {
    if (!selectedWell) return;

    let cancelled = false;

    async function loadHistory() {
      try {
        setHistoryLoading(true);

        const result = await getDecisionHistory(
          selectedWell
        );

        if (!cancelled) {
          setDecisionHistory(result);
        }
      } catch (err) {
        console.error(
          "Failed to load engineer decision history:",
          err
        );

        if (!cancelled) {
          setDecisionHistory(null);
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false);
        }
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [selectedWell, historyRefreshKey]);

  // ----------------------------------------------------------
  // Load telemetry history
  // ----------------------------------------------------------

  useEffect(() => {
    if (!selectedWell) return;

    let cancelled = false;

    async function loadTelemetryHistory() {
      try {
        setTelemetryHistoryLoading(true);

        const result = await getTelemetryHistory(
          selectedWell,
          144
        );

        if (!cancelled) {
          setTelemetryHistory(result);
        }
      } catch (err) {
        console.error(
          "Failed to load telemetry history:",
          err
        );

        if (!cancelled) {
          setTelemetryHistory([]);
        }
      } finally {
        if (!cancelled) {
          setTelemetryHistoryLoading(false);
        }
      }
    }

    loadTelemetryHistory();

    return () => {
      cancelled = true;
    };
  }, [selectedWell]);
  useEffect(() => {
  let cancelled = false;

  async function loadSystemHealth() {
    try {
      setSystemHealthLoading(true);

      const result = await getSystemHealth();

      if (!cancelled) {
        setSystemHealth(result);
      }
    } catch (err) {
      console.error(
        "Failed to load system health:",
        err
      );

      if (!cancelled) {
        setSystemHealth(null);
      }
    } finally {
      if (!cancelled) {
        setSystemHealthLoading(false);
      }
    }
  }

  loadSystemHealth();

  const interval = window.setInterval(
    loadSystemHealth,
    15000
  );

  return () => {
    cancelled = true;
    window.clearInterval(interval);
  };
}, []);

  // ----------------------------------------------------------
  // Navigation
  // ----------------------------------------------------------

  function changeSection(section: ActiveSection) {
    setActiveSection(section);
    setError(null);
  }

  // ----------------------------------------------------------
  // What-If
  // ----------------------------------------------------------

  async function handleWhatIf() {
    if (!selectedWell) return;

    try {
      setRunningWhatIf(true);
      setError(null);

      const result = await runWhatIf(
        selectedWell,
        scenario
      );

      setWhatIfResult(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "What-If simulation failed"
      );
    } finally {
      setRunningWhatIf(false);
    }
  }

  function updateScenario(
    field: keyof Scenario,
    value: string
  ) {
    setScenario((current) => ({
      ...current,
      [field]: Number(value),
    }));
  }

  function resetScenario() {
    const recommendation =
      data?.optimization?.recommendation;

    if (!recommendation) return;

    setScenario({
      steam_rate: recommendation.steam_rate,
      steam_temperature:
        recommendation.steam_temperature,
      injection_pressure:
        recommendation.injection_pressure,
      injection_duration:
        recommendation.injection_duration,
      soak_time: recommendation.soak_time,
      stroke_length: recommendation.stroke_length,
      spm: recommendation.spm,
      vfd_frequency:
        recommendation.vfd_frequency,
    });

    setWhatIfResult(null);
  }

  // ----------------------------------------------------------
  // Engineer Review
  // ----------------------------------------------------------

  async function handleEngineerDecision(
    decision: "APPROVE" | "MODIFY" | "REJECT"
  ) {
    if (!optimizationData) {
      setError(
        "No optimization recommendation available."
      );
      return;
    }

    if (
      decision === "REJECT" &&
      !rejectionReason.trim()
    ) {
      setError("Please provide a rejection reason.");
      return;
    }

    try {
      setDecisionBusy(true);
      setError(null);

      const modifiedParameters =
        decision === "MODIFY"
          ? {
              steam_rate: scenario.steam_rate,
              steam_temperature:
                scenario.steam_temperature,
              injection_pressure:
                scenario.injection_pressure,
              injection_duration:
                scenario.injection_duration,
              soak_time: scenario.soak_time,
              stroke_length: scenario.stroke_length,
              spm: scenario.spm,
              vfd_frequency:
                scenario.vfd_frequency,
            }
          : undefined;

      const result =
        await submitEngineerDecision(
          selectedWell,
          {
            recommendation_id:
              optimizationData.recommendation_id,
            decision,
            modified_parameters:
              modifiedParameters,
            rejection_reason:
              decision === "REJECT"
                ? rejectionReason.trim()
                : undefined,
            notes:
              decision === "APPROVE"
                ? "Engineer approved the AI recommendation."
                : decision === "MODIFY"
                  ? "Engineer modified the recommendation and requested re-simulation."
                  : "Engineer rejected the recommendation.",
          }
        );

      setDecisionResult(result);
      setShowRejectBox(false);
      setRejectionReason("");

      // Refresh the persistent audit trail immediately.
      setHistoryRefreshKey(
        (current) => current + 1
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to record engineer decision."
      );
    } finally {
      setDecisionBusy(false);
    }
  }

  // ----------------------------------------------------------
  // Shared UI
  // ----------------------------------------------------------

  function renderTopBar() {
    const meta = sectionMeta[activeSection];

    return (
      <header className="topbar">
        <div>
          <h1>WELLWISE</h1>
          <p>AI-Powered Baghewala Digital Twin</p>

          <div className="topbar-section">
            <strong>{meta.title}</strong>
            <span>{meta.subtitle}</span>
          </div>
        </div>

        <div className="topbar-actions">
          <select
            className="well-selector"
            value={selectedWell}
            onChange={(event) => {
              setSelectedWell(event.target.value);
              setScenarioWellId("");
              setWhatIfResult(null);
              setOptimizationData(null);
              setDecisionResult(null);
              setShowRejectBox(false);
              setRejectionReason("");
              setError(null);
            }}
            disabled={
              loadingTwin || wells.length === 0
            }
          >
            {wells.map((well) => (
              <option
                key={well.well_id}
                value={well.well_id}
              >
                {well.well_id}
              </option>
            ))}
          </select>

          <div className="system-status">
            <span className="status-dot" />
            SIMULATED TELEMETRY
          </div>
        </div>
      </header>
    );
  }

  function renderWellHeader() {
    if (!data) return null;

    return (
      <section className="well-header">
        <div>
          <h2>{data.well.well_id}</h2>
          <p>{data.well.reservoir}</p>
          <small>{data.well.formation}</small>
        </div>

        <div className="active-badge">
          {data.well.status}
        </div>
      </section>
    );
  }

  function renderMetric(
    label: string,
    value: string
  ) {
    return (
      <div className="metric-card" key={label}>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    );
  }

  function renderCurrentState() {
    if (!data) return null;

    return (
      <section className="section">
        <div className="section-heading">
          <h3>Current Reservoir State</h3>
          <span>Live</span>
        </div>

        <div className="metrics-grid">
          {renderMetric(
            "Reservoir Temperature",
            `${data.telemetry.reservoir_temperature.toFixed(
              2
            )} °C`
          )}

          {renderMetric(
            "Reservoir Pressure",
            data.telemetry.reservoir_pressure.toFixed(
              2
            )
          )}

          {renderMetric(
            "Current Oil Rate",
            `${data.telemetry.oil_rate.toFixed(
              2
            )} BOPD`
          )}

          {renderMetric(
            "Oil Viscosity",
            data.telemetry.oil_viscosity.toFixed(0)
          )}
        </div>
      </section>
    );
  }

  function renderDigitalTwinPrediction() {
    if (!data) return null;

    return (
      <section className="section">
        <div className="section-heading">
          <h3>24h Digital Twin Prediction</h3>
          <span>3 XGBoost Models</span>
        </div>

        <div className="metrics-grid">
          {renderMetric(
            "Predicted Temperature",
            `${data.prediction_24h.reservoir_temperature.toFixed(
              2
            )} °C`
          )}

          {renderMetric(
            "Predicted Oil Rate",
            `${data.prediction_24h.oil_rate.toFixed(
              2
            )} BOPD`
          )}

          {renderMetric(
            "Rod Floating Risk",
            `${data.prediction_24h.rod_floating_risk_pct.toFixed(
              2
            )}%`
          )}

          {renderMetric(
            "Rod Status",
            data.prediction_24h.rod_status
          )}
        </div>
      </section>
    );
  }

  function renderSrpState() {
    if (!data) return null;

    return (
      <section className="section">
        <div className="section-heading">
          <h3>SRP Operating State</h3>
          <span>Current</span>
        </div>

        <div className="metrics-grid">
          {renderMetric(
            "SPM",
            data.telemetry.spm.toFixed(2)
          )}

          {renderMetric(
            "Stroke Length",
            data.telemetry.stroke_length.toFixed(1)
          )}

          {renderMetric(
            "VFD Frequency",
            `${data.telemetry.vfd_frequency.toFixed(
              2
            )} Hz`
          )}

          {renderMetric(
            "Pump Fillage",
            `${data.telemetry.pump_fillage.toFixed(
              2
            )}%`
          )}
        </div>
      </section>
    );
  }

  function renderMechanicalState() {
    if (!data) return null;

    return (
      <section className="section">
        <div className="section-heading">
          <h3>Mechanical Condition</h3>
          <span>Current</span>
        </div>

        <div className="metrics-grid">
          {renderMetric(
            "Rod Load",
            data.telemetry.rod_load.toFixed(2)
          )}

          {renderMetric(
            "Pump Load",
            data.telemetry.pump_load.toFixed(2)
          )}

          {renderMetric(
            "Fluid Level",
            data.telemetry.fluid_level.toFixed(2)
          )}

          {renderMetric(
            "Energy",
            data.telemetry.energy.toFixed(2)
          )}
        </div>
      </section>
    );
  }

  function renderDashboard() {
  if (!data) return null;

  const currentOil = data.telemetry.oil_rate;
  const predictedOil = data.prediction_24h.oil_rate;

  const currentTemp =
    data.telemetry.reservoir_temperature;

  const predictedTemp =
    data.prediction_24h.reservoir_temperature;

  const oilDelta = predictedOil - currentOil;
  const tempDelta = predictedTemp - currentTemp;

  const rodRisk =
    data.prediction_24h.rod_floating_risk_pct;

  const elevatedRodRisk = rodRisk >= 50;

  return (
    <>
      {/* =========================================
          CURRENT WELL STATUS
          ========================================= */}

      <section className="dashboard-hero">
        <div className="dashboard-hero-main">
          <div className="dashboard-hero-kicker">
            ACTIVE WELL
          </div>

          <div className="dashboard-hero-title">
            <h2>{data.well.well_id}</h2>

            <span className="dashboard-active-dot">
              ●
            </span>

            <span>{data.well.status}</span>
          </div>

          <p>
            {data.well.reservoir} ·{" "}
            {data.well.formation}
          </p>
        </div>

        <div className="dashboard-hero-meta">
          <span>SIMULATED TELEMETRY</span>

          <small>
            Updated{" "}
            {formatDateTime(
              data.telemetry.timestamp
            )}
          </small>
        </div>
      </section>

      {/* =========================================
          KEY METRICS
          ========================================= */}

      <section className="dashboard-key-metrics">
        <div className="key-metric featured">
          <span>Current Oil Rate</span>

          <strong>
            {currentOil.toFixed(2)}{" "}
            <small>BOPD</small>
          </strong>

          <p>
            24h prediction{" "}
            <b>{predictedOil.toFixed(2)} BOPD</b>
          </p>
        </div>

        <div className="key-metric">
          <span>Reservoir Temperature</span>

          <strong>
            {currentTemp.toFixed(2)}{" "}
            <small>°C</small>
          </strong>

          <p>
            24h{" "}
            <b>
              {tempDelta >= 0 ? "+" : ""}
              {tempDelta.toFixed(2)} °C
            </b>
          </p>
        </div>

        <div className="key-metric">
          <span>Reservoir Pressure</span>

          <strong>
            {data.telemetry.reservoir_pressure.toFixed(
              2
            )}
          </strong>

          <p>
            Current reservoir state
          </p>
        </div>

        <div
          className={`key-metric ${
            elevatedRodRisk
              ? "key-metric-warning"
              : ""
          }`}
        >
          <span>24h Rod Floating Risk</span>

          <strong>
            {rodRisk.toFixed(2)}
            <small>%</small>
          </strong>

          <p>
            {data.prediction_24h.rod_status}
          </p>
        </div>
      </section>

      {/* =========================================
          MAIN TWO-COLUMN AREA
          ========================================= */}

      <section className="dashboard-main-grid">

        {/* Operating State */}

        <div className="dashboard-panel-large">
          <div className="dashboard-panel-header">
            <div>
              <span className="dashboard-panel-kicker">
                LIVE OPERATING STATE
              </span>

              <h3>SRP Performance</h3>
            </div>

            <span className="dashboard-panel-status">
              LIVE
            </span>
          </div>

          <div className="operating-list">
            <div className="operating-row">
              <span>Pump Fillage</span>

              <strong>
                {data.telemetry.pump_fillage.toFixed(
                  2
                )}
                %
              </strong>
            </div>

            <div className="operating-row">
              <span>SPM</span>

              <strong>
                {data.telemetry.spm.toFixed(2)}
              </strong>
            </div>

            <div className="operating-row">
              <span>Stroke Length</span>

              <strong>
                {data.telemetry.stroke_length.toFixed(
                  0
                )}
              </strong>
            </div>

            <div className="operating-row">
              <span>VFD Frequency</span>

              <strong>
                {data.telemetry.vfd_frequency.toFixed(
                  2
                )}{" "}
                Hz
              </strong>
            </div>

            <div className="operating-row">
              <span>Energy</span>

              <strong>
                {data.telemetry.energy.toFixed(2)}
              </strong>
            </div>

            <div className="operating-row">
              <span>Fluid Level</span>

              <strong>
                {data.telemetry.fluid_level.toFixed(
                  2
                )}
              </strong>
            </div>
          </div>
        </div>

        {/* Digital Twin Outlook */}

        <div className="dashboard-panel-large">
          <div className="dashboard-panel-header">
            <div>
              <span className="dashboard-panel-kicker">
                DIGITAL TWIN
              </span>

              <h3>24h Outlook</h3>
            </div>

            <span className="dashboard-panel-status">
              3 MODELS
            </span>
          </div>

          <div className="outlook-list">
            <div className="outlook-row">
              <div>
                <span>Oil Rate</span>

                <small>
                  Current {currentOil.toFixed(2)} BOPD
                </small>
              </div>

              <strong>
                {predictedOil.toFixed(2)}
                <small>BOPD</small>
              </strong>

              <em
                className={
                  oilDelta >= 0
                    ? "trend-positive"
                    : "trend-negative"
                }
              >
                {oilDelta >= 0 ? "+" : ""}
                {oilDelta.toFixed(2)}
              </em>
            </div>

            <div className="outlook-row">
              <div>
                <span>Reservoir Temperature</span>

                <small>
                  Current {currentTemp.toFixed(2)} °C
                </small>
              </div>

              <strong>
                {predictedTemp.toFixed(2)}
                <small>°C</small>
              </strong>

              <em
                className={
                  tempDelta >= 0
                    ? "trend-positive"
                    : "trend-negative"
                }
              >
                {tempDelta >= 0 ? "+" : ""}
                {tempDelta.toFixed(2)}
              </em>
            </div>

            <div className="outlook-row">
              <div>
                <span>Rod Floating Risk</span>

                <small>
                  Predicted probability
                </small>
              </div>

              <strong>
                {rodRisk.toFixed(2)}
                <small>%</small>
              </strong>

              <em
                className={
                  elevatedRodRisk
                    ? "trend-warning"
                    : "trend-neutral"
                }
              >
                {data.prediction_24h.rod_status}
              </em>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================
          ATTENTION STRIP
          ========================================= */}

      <section className="dashboard-attention">
        <div className="attention-main">
          <div
            className={`attention-indicator ${
              elevatedRodRisk
                ? "warning"
                : "neutral"
            }`}
          />
          
          <div>
            <span>
              {elevatedRodRisk
                ? "ATTENTION REQUIRED"
                : "SYSTEM MONITORED"}
            </span>

            <strong>
              {elevatedRodRisk
                ? "Elevated rod floating risk detected in the 24h model prediction."
                : "No elevated rod floating risk in the current model prediction."}
            </strong>
          </div>
        </div>

        <div className="attention-meta">
          <span>CONTROL MODE</span>

          <strong>
            MANUAL / ENGINEER REVIEW
          </strong>
        </div>
      </section>

      {/* =========================================
          QUICK ACTIONS
          ========================================= */}

      <section className="dashboard-actions">
        <div className="dashboard-actions-header">
          <div>
            <span className="dashboard-panel-kicker">
              WORKFLOW
            </span>

            <h3>Quick Actions</h3>
          </div>
        </div>

        <div className="dashboard-action-row">
          <button
            type="button"
            onClick={() =>
              changeSection("digital-twin")
            }
          >
            <span>01</span>
            Digital Twin
          </button>

          <button
            type="button"
            onClick={() =>
              changeSection("what-if")
            }
          >
            <span>02</span>
            What-If Simulation
          </button>

          <button
            type="button"
            onClick={() =>
              changeSection("optimization")
            }
          >
            <span>03</span>
            Optimization
          </button>

          <button
            type="button"
            onClick={() =>
              changeSection("review")
            }
          >
            <span>04</span>
            Engineer Review
          </button>
        </div>
      </section>
    </>
  );
}

  function renderDigitalTwin() {
    return (
      <>
        {renderCurrentState()}
        {renderDigitalTwinPrediction()}
        {renderSrpState()}
        {renderMechanicalState()}
      </>
    );
  }

  function renderWhatIf() {
    return (
      <section className="section">
        <div className="section-heading">
          <h3>What-If Simulation</h3>
          <span>Engineer Controlled</span>
        </div>

        <div className="what-if-card">
          <div className="what-if-intro">
            <strong>
              Test a custom operating scenario
            </strong>
            <p>
              Change CSS and SRP parameters to see how
              the trained models respond. Nothing is
              applied or saved automatically.
            </p>
          </div>

          <div className="what-if-grid">
            {(
              [
                ["steam_rate", "Steam Rate", "t/hr", "0.1"],
                [
                  "steam_temperature",
                  "Steam Temperature",
                  "°F",
                  "1",
                ],
                [
                  "injection_pressure",
                  "Injection Pressure",
                  "psi",
                  "0.5",
                ],
                [
                  "injection_duration",
                  "Injection Duration",
                  "hr",
                  "1",
                ],
                [
                  "soak_time",
                  "Soak Time",
                  "hr",
                  "1",
                ],
                [
                  "stroke_length",
                  "Stroke Length",
                  "in",
                  "1",
                ],
                ["spm", "SPM", "strokes/min", "0.25"],
                [
                  "vfd_frequency",
                  "VFD Frequency",
                  "Hz",
                  "0.01",
                ],
              ] as Array<
                [keyof Scenario, string, string, string]
              >
            ).map(([field, label, unit, step]) => (
              <label
                className="scenario-field"
                key={field}
              >
                <div className="scenario-field-label">
                  <span>{label}</span>
                  <small>{unit}</small>
                </div>

                <input
                  type="number"
                  step={step}
                  value={scenario[field]}
                  onChange={(event) =>
                    updateScenario(
                      field,
                      event.target.value
                    )
                  }
                />
              </label>
            ))}
          </div>

          <div className="what-if-actions">
            <button
              className="what-if-button"
              type="button"
              onClick={handleWhatIf}
              disabled={
                runningWhatIf || !selectedWell
              }
            >
              {runningWhatIf
                ? "Running Simulation..."
                : "Run What-If Simulation"}
            </button>

            <button
              className="scenario-reset-button"
              type="button"
              onClick={resetScenario}
            >
              Reset to AI Recommendation
            </button>
          </div>

          {whatIfResult && (
            <div className="what-if-result">
              <div className="result-title">
                <div>
                  <strong>
                    Simulation Result
                  </strong>
                  <span>
                    {whatIfResult.simulation_type}
                  </span>
                </div>
                <span>NOT SAVED</span>
              </div>

              <div className="comparison-grid">
                <div className="comparison-panel">
                  <h4>Baseline</h4>

                  <div>
                    <span>Temperature</span>
                    <strong>
                      {whatIfResult.baseline.temperature.toFixed(
                        2
                      )}{" "}
                      °C
                    </strong>
                  </div>

                  <div>
                    <span>Oil Rate</span>
                    <strong>
                      {whatIfResult.baseline.oil_rate.toFixed(
                        2
                      )}{" "}
                      BOPD
                    </strong>
                  </div>

                  <div>
                    <span>Rod Risk</span>
                    <strong>
                      {whatIfResult.baseline.rod_risk_pct.toFixed(
                        2
                      )}
                      %
                    </strong>
                  </div>

                  <div>
                    <span>Energy</span>
                    <strong>
                      {whatIfResult.baseline.energy.toFixed(
                        2
                      )}
                    </strong>
                  </div>
                </div>

                <div className="comparison-panel">
                  <h4>What-If Result</h4>

                  <div>
                    <span>Temperature</span>
                    <strong>
                      {whatIfResult.predicted_outcome.temperature.toFixed(
                        2
                      )}{" "}
                      °C
                    </strong>
                  </div>

                  <div>
                    <span>Oil Rate</span>
                    <strong>
                      {whatIfResult.predicted_outcome.oil_rate.toFixed(
                        2
                      )}{" "}
                      BOPD
                    </strong>
                  </div>

                  <div>
                    <span>Rod Risk</span>
                    <strong>
                      {whatIfResult.predicted_outcome.rod_risk_pct.toFixed(
                        2
                      )}
                      %
                    </strong>
                  </div>

                  <div>
                    <span>Energy</span>
                    <strong>
                      {whatIfResult.predicted_outcome.energy.toFixed(
                        2
                      )}
                    </strong>
                  </div>
                </div>
              </div>

              <div className="changes-grid">
                <div>
                  <span>Oil Change</span>
                  <strong>
                    {signedPct(
                      whatIfResult.changes_vs_baseline
                        .oil_change_pct
                    )}
                  </strong>
                </div>

                <div>
                  <span>Risk Change</span>
                  <strong>
                    {signedPct(
                      whatIfResult.changes_vs_baseline
                        .risk_change_pct
                    )}
                  </strong>
                </div>

                <div>
                  <span>Energy Change</span>
                  <strong>
                    {signedPct(
                      whatIfResult.changes_vs_baseline
                        .energy_change_pct
                    )}
                  </strong>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    );
  }

  function renderOptimizationCard(
    recommendation: NonNullable<
      OptimizationResponse["recommendation"]
    >
  ) {
    return (
      <div className="optimization-v2-card">
        {/* HEADER */}
        <div className="optimization-v2-header">
          <div>
            <span className="optimization-v2-eyebrow">
              WELLWISE OPTIMIZER · V2.1
            </span>

            <div className="optimization-v2-title-row">
              <h3>Recommended Operating Point</h3>

              <span className="optimization-v2-feasible">
                FEASIBLE
              </span>
            </div>

            <p>
              Optimized CSS cycle and SRP operating parameters
              for the selected well.
            </p>
          </div>

          <div className="optimization-v2-score">
            <span>OPTIMIZATION SCORE</span>
            <strong>
              {recommendation.optimization_score.toFixed(3)}
            </strong>
          </div>
        </div>

        {/* OPERATING PARAMETERS */}
        <div className="optimization-v2-sections">
          {/* CSS */}
          <div className="optimization-v2-section">
            <div className="optimization-v2-section-header">
              <div>
                <span>01</span>
                <div>
                  <strong>CSS Cycle</strong>
                  <small>Steam injection parameters</small>
                </div>
              </div>
            </div>

            <div className="optimization-v2-parameter-list">
              <div className="optimization-v2-parameter">
                <span>Steam Rate</span>
                <strong>{recommendation.steam_rate}</strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>Steam Temperature</span>
                <strong>
                  {recommendation.steam_temperature} °F
                </strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>Injection Pressure</span>
                <strong>
                  {recommendation.injection_pressure}
                </strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>Injection Duration</span>
                <strong>
                  {recommendation.injection_duration} hr
                </strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>Soak Time</span>
                <strong>
                  {recommendation.soak_time} hr
                </strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>Steam Volume</span>
                <strong>
                  {recommendation.steam_volume.toFixed(1)}
                </strong>
              </div>
            </div>
          </div>

          {/* SRP */}
          <div className="optimization-v2-section">
            <div className="optimization-v2-section-header">
              <div>
                <span>02</span>
                <div>
                  <strong>SRP Controls</strong>
                  <small>Rod pump operating point</small>
                </div>
              </div>
            </div>

            <div className="optimization-v2-parameter-list">
              <div className="optimization-v2-parameter">
                <span>Stroke Length</span>
                <strong>
                  {recommendation.stroke_length}
                </strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>SPM</span>
                <strong>{recommendation.spm}</strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>VFD Frequency</span>
                <strong>
                  {recommendation.vfd_frequency.toFixed(2)} Hz
                </strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>Pump Energy</span>
                <strong>
                  {recommendation.predicted_energy.toFixed(1)}
                </strong>
              </div>

              <div className="optimization-v2-parameter">
                <span>SOR Proxy</span>
                <strong>
                  {recommendation.sor_proxy.toFixed(2)}
                </strong>
              </div>
            </div>
          </div>
        </div>

        {/* PREDICTED OUTCOMES */}
        <div className="optimization-v2-results">
          <div className="optimization-v2-results-header">
            <div>
              <span>03</span>
              <div>
                <strong>Predicted 24h Outcome</strong>
                <small>
                  Model-estimated response to the operating point
                </small>
              </div>
            </div>
          </div>

          <div className="optimization-v2-result-grid">
            <div className="optimization-v2-result featured">
              <span>Oil Rate</span>
              <strong>
                {recommendation.predicted_oil_rate.toFixed(2)}
                <small>BOPD</small>
              </strong>
            </div>

            <div className="optimization-v2-result">
              <span>Reservoir Temperature</span>
              <strong>
                {recommendation.predicted_temperature.toFixed(
                  2
                )}
                <small>°C</small>
              </strong>
            </div>

            <div className="optimization-v2-result warning">
              <span>Rod Floating Risk</span>
              <strong>
                {recommendation.predicted_rod_risk.toFixed(2)}
                <small>%</small>
              </strong>
            </div>

            <div className="optimization-v2-result">
              <span>Energy</span>
              <strong>
                {recommendation.predicted_energy.toFixed(1)}
              </strong>
            </div>
          </div>
        </div>

        {/* IMPACT */}
        <div className="optimization-v2-impact">
          <div className="optimization-v2-impact-header">
            <div>
              <span>04</span>
              <div>
                <strong>Impact vs Current State</strong>
                <small>Expected change from baseline</small>
              </div>
            </div>

            <span className="optimization-v2-candidates">
              {optimizationData?.feasible_candidates ?? 0} feasible
              candidates
            </span>
          </div>

          <div className="optimization-v2-impact-grid">
            <div>
              <span>Oil Rate</span>
              <strong>
                {signedPct(recommendation.oil_change_pct)}
              </strong>
            </div>

            <div>
              <span>Rod Risk</span>
              <strong>
                {signedPct(recommendation.risk_change_pct)}
              </strong>
            </div>

            <div>
              <span>Energy</span>
              <strong>
                {signedPct(recommendation.energy_change_pct)}
              </strong>
            </div>
          </div>
        </div>
      </div>
    );
  }

  function renderOptimization() {
    const recommendation =
      optimizationData?.recommendation;

    return (
      <section className="section">
        <div className="section-heading">
          <h3>AI Optimization</h3>
          <span>
            {optimizationData?.status ?? "Loading"}
          </span>
        </div>

        {loadingOptimization &&
        !optimizationData ? (
          <div className="empty-card">
            Running WellWise optimization...
          </div>
        ) : recommendation ? (
          renderOptimizationCard(recommendation)
        ) : (
          <div className="empty-card">
            No feasible recommendation available.
          </div>
        )}
      </section>
    );
  }

  function renderEngineerReview() {
    const recommendation =
      optimizationData?.recommendation;

    return (
      <>
        <section className="section">
          <div className="section-heading">
            <h3>AI Recommendation</h3>
            <span>
              {optimizationData?.status ?? "Loading"}
            </span>
          </div>

          {loadingOptimization &&
          !optimizationData ? (
            <div className="empty-card">
              Loading recommendation...
            </div>
          ) : recommendation ? (
            renderOptimizationCard(recommendation)
          ) : (
            <div className="empty-card">
              No recommendation available for review.
            </div>
          )}
        </section>

        <section className="section">
          <div className="engineer-review">
            <div className="engineer-review-header">
              <div>
                <strong>Engineer Review</strong>
                <p>
                  Review the AI-generated
                  recommendation before any
                  operational decision.
                </p>
              </div>

              <span className="review-state">
                HUMAN REVIEW
              </span>
            </div>

            {!recommendation ? (
              <div className="empty-card">
                No recommendation is available for
                review.
              </div>
            ) : (
              <><div className="review-workflow">
  <div className="workflow-step active">
    <span>01</span>
    <div>
      <strong>AI Recommendation</strong>
      <small>Generated by optimizer</small>
    </div>
  </div>

  <div className="workflow-line" />

  <div className="workflow-step active">
    <span>02</span>
    <div>
      <strong>Engineer Review</strong>
      <small>Human validation required</small>
    </div>
  </div>

  <div className="workflow-line" />

  <div
    className={`workflow-step ${
      decisionResult ? "active" : "pending"
    }`}
  >
    <span>03</span>
    <div>
      <strong>
        {decisionResult
          ? `Decision: ${decisionResult.decision}`
          : "Awaiting Decision"}
      </strong>

      <small>
        {decisionResult
          ? "Recorded in audit history"
          : "Approve, modify or reject"}
      </small>
    </div>
  </div>
</div>
                <div className="review-context">
                  <span>Recommendation</span>
                  <strong>
                    #{optimizationData?.recommendation_id}
                  </strong>
                  <p>
                    For MODIFY, WellWise stores the
                    current What-If values and returns a
                    re-simulation without applying any
                    operating change.
                  </p>
                </div>

                <div className="review-actions">
                  <button
                    type="button"
                    className="review-button approve"
                    onClick={() =>
                      handleEngineerDecision(
                        "APPROVE"
                      )
                    }
                    disabled={
                      decisionBusy ||
                      !!decisionResult
                    }
                  >
                    {decisionBusy
                      ? "Processing..."
                      : "Approve"}
                  </button>

                  <button
                    type="button"
                    className="review-button modify"
                    onClick={() =>
                      handleEngineerDecision(
                        "MODIFY"
                      )
                    }
                    disabled={
                      decisionBusy ||
                      !!decisionResult
                    }
                  >
                    Modify & Re-simulate
                  </button>

                  <button
                    type="button"
                    className="review-button reject"
                    onClick={() =>
                      setShowRejectBox(true)
                    }
                    disabled={
                      decisionBusy ||
                      !!decisionResult
                    }
                  >
                    Reject
                  </button>
                </div>

                <div className="review-helper">
                  <span>
                    Modify workflow
                  </span>
                  <p>
                    Change the values in What-If
                    Simulation, run the scenario, then
                    return here to record the modified
                    decision.
                  </p>
                </div>

                {showRejectBox &&
                  !decisionResult && (
                    <div className="reject-box">
                      <label>
                        Rejection Reason
                        <textarea
                          value={rejectionReason}
                          onChange={(event) =>
                            setRejectionReason(
                              event.target.value
                            )
                          }
                          placeholder="Enter the reason for rejecting this recommendation..."
                          rows={4}
                        />
                      </label>

                      <div className="reject-actions">
                        <button
                          type="button"
                          className="review-button reject"
                          onClick={() =>
                            handleEngineerDecision(
                              "REJECT"
                            )
                          }
                          disabled={decisionBusy}
                        >
                          Confirm Rejection
                        </button>

                        <button
                          type="button"
                          className="cancel-button"
                          onClick={() => {
                            setShowRejectBox(false);
                            setRejectionReason("");
                          }}
                          disabled={decisionBusy}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                {decisionResult && (
                  <div className="decision-result">
                    <div className="decision-result-header">
                      <strong>
                        Decision Recorded
                      </strong>
                      <span>
                        #{decisionResult.decision_id}
                      </span>
                    </div>

                    <p>
                      Engineer decision:{" "}
                      <strong>
                        {decisionResult.decision}
                      </strong>
                    </p>

                    {decisionResult.modified_simulation && (
                      <div className="modified-result">
                        <strong>
                          Modified Scenario Result
                        </strong>

                        <div className="optimization-impact">
                          <div>
                            <span>Oil Rate</span>
                            <strong>
                              {decisionResult
                                .modified_simulation
                                .predicted_outcome
                                .oil_rate.toFixed(2)}{" "}
                              BOPD
                            </strong>
                          </div>

                          <div>
                            <span>Rod Risk</span>
                            <strong>
                              {decisionResult
                                .modified_simulation
                                .predicted_outcome
                                .rod_risk_pct.toFixed(2)}
                              %
                            </strong>
                          </div>

                          <div>
                            <span>Energy</span>
                            <strong>
                              {decisionResult
                                .modified_simulation
                                .predicted_outcome
                                .energy.toFixed(2)}
                            </strong>
                          </div>

                          <div>
                            <span>Oil Change</span>
                            <strong>
                              {signedPct(
                                decisionResult
                                  .modified_simulation
                                  .changes_vs_baseline
                                  .oil_change_pct
                              )}
                            </strong>
                          </div>

                          <div>
                            <span>Risk Change</span>
                            <strong>
                              {signedPct(
                                decisionResult
                                  .modified_simulation
                                  .changes_vs_baseline
                                  .risk_change_pct
                              )}
                            </strong>
                          </div>

                          <div>
                            <span>Energy Change</span>
                            <strong>
                              {signedPct(
                                decisionResult
                                  .modified_simulation
                                  .changes_vs_baseline
                                  .energy_change_pct
                              )}
                            </strong>
                          </div>
                        </div>

                        <p className="simulation-note">
                          Modified scenario was simulated
                          only. No operating change was
                          applied automatically.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </section>

        <div className="engineer-note">
          <strong>
            Human-in-the-loop control
          </strong>
          <p>
            WellWise provides decision support only.
            Operational changes are not executed
            automatically.
          </p>
        </div>
      </>
    );
  }

  function renderHistory() {
    return (
      <>
        <section className="section">
          <div className="section-heading">
            <h3>Telemetry Trends</h3>
            <span>
              Last 24h · 10-minute sampling
            </span>
          </div>

          <div className="trend-controls">
            {(
              Object.keys(trendMeta) as TrendKey[]
            ).map((metric) => (
              <button
                key={metric}
                type="button"
                className={
                  trendMetric === metric
                    ? "trend-button active"
                    : "trend-button"
                }
                onClick={() =>
                  setTrendMetric(metric)
                }
              >
                {trendMeta[metric].label}
              </button>
            ))}
          </div>

          <div className="trend-card">
            <div className="trend-title">
              <div>
                <strong>
                  {trendMeta[trendMetric].label}
                </strong>
                <span>
                  Historical telemetry for{" "}
                  {selectedWell}
                </span>
              </div>

              <span>
                {telemetryHistory.length} points
              </span>
            </div>

            {telemetryHistoryLoading ? (
              <div className="trend-empty">
                Loading historical telemetry...
              </div>
            ) : (
              <TrendChart
                data={telemetryHistory}
                metric={trendMetric}
              />
            )}
          </div>
        </section>

        <section className="section">
          <div className="section-heading">
            <h3>Engineer Review History</h3>
            <span>
              {historyLoading
                ? "Loading..."
                : `${decisionHistory?.count ?? 0} reviews`}
            </span>
          </div>

          {historyLoading ? (
            <div className="history-empty">
              Loading engineer review history...
            </div>
          ) : !decisionHistory ||
            decisionHistory.history.length === 0 ? (
            <div className="history-empty">
              No engineer review decisions have been
              recorded for this well yet.
            </div>
          ) : (
            <div className="history-list">
              {decisionHistory.history.map(
                (item) => (
                  <article
                    key={item.decision_id}
                    className={`history-card history-${item.decision.toLowerCase()}`}
                  >
                    <div className="history-card-header">
                      <div className="history-decision">
                        <span className="history-indicator" />

                        <div>
                          <strong>
                            {item.decision}
                          </strong>

                          <span>
                            Recommendation #
                            {item.recommendation_id ??
                              "—"}
                          </span>
                        </div>
                      </div>

                      <time>
                        {formatDateTime(
                          item.created_at
                        )}
                      </time>
                    </div>

                    {item.decision ===
                      "APPROVE" &&
                      item.recommendation && (
                        <div className="history-content">
                          <h4>
                            Accepted operating point
                          </h4>

                          <div className="history-parameters">
                            <div>
                              <span>Steam Rate</span>
                              <strong>
                                {
                                  item
                                    .recommendation
                                    .steam_rate
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Steam Temperature
                              </span>
                              <strong>
                                {
                                  item
                                    .recommendation
                                    .steam_temperature
                                }{" "}
                                °F
                              </strong>
                            </div>

                            <div>
                              <span>
                                Injection Pressure
                              </span>
                              <strong>
                                {
                                  item
                                    .recommendation
                                    .injection_pressure
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Injection Duration
                              </span>
                              <strong>
                                {
                                  item
                                    .recommendation
                                    .injection_duration
                                }{" "}
                                hr
                              </strong>
                            </div>

                            <div>
                              <span>Soak Time</span>
                              <strong>
                                {
                                  item
                                    .recommendation
                                    .soak_time
                                }{" "}
                                hr
                              </strong>
                            </div>

                            <div>
                              <span>
                                Stroke Length
                              </span>
                              <strong>
                                {
                                  item
                                    .recommendation
                                    .stroke_length
                                }
                              </strong>
                            </div>

                            <div>
                              <span>SPM</span>
                              <strong>
                                {
                                  item
                                    .recommendation
                                    .spm
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                VFD Frequency
                              </span>
                              <strong>
                                {
                                  item
                                    .recommendation
                                    .vfd_frequency
                                }{" "}
                                Hz
                              </strong>
                            </div>
                          </div>
                        </div>
                      )}

                    {item.decision === "MODIFY" && (
                      <div className="history-content">
                        <h4>
                          Modified parameters
                        </h4>

                        {item.modified_parameters &&
                        Object.keys(
                          item.modified_parameters
                        ).length > 0 ? (
                          <div className="history-changes">
                            {(
                              Object.entries(
                                item.modified_parameters as Record<
                                  string,
                                  number
                                >
                              ) as Array<
                                [string, number]
                              >
                            ).map(
                              ([key, value]) => (
                                <div
                                  key={key}
                                  className="history-change"
                                >
                                  <span>
                                    {formatParameterName(
                                      key
                                    )}
                                  </span>

                                  <strong>
                                    {value}
                                    {key ===
                                      "steam_temperature" &&
                                      " °F"}
                                    {key ===
                                      "injection_duration" &&
                                      " hr"}
                                    {key ===
                                      "soak_time" &&
                                      " hr"}
                                    {key ===
                                      "vfd_frequency" &&
                                      " Hz"}
                                  </strong>
                                </div>
                              )
                            )}
                          </div>
                        ) : (
                          <p>
                            No modified parameters
                            recorded.
                          </p>
                        )}

                        {item.recommendation && (
                          <div className="history-original">
                            <span>
                              Original recommendation
                            </span>

                            <div>
                              SPM{" "}
                              {
                                item.recommendation
                                  .spm
                              }{" "}
                              · Stroke{" "}
                              {
                                item.recommendation
                                  .stroke_length
                              }
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {item.decision === "REJECT" && (
                      <div className="history-content">
                        <h4>
                          Rejection reason
                        </h4>

                        <div className="history-reason">
                          {item.rejection_reason ||
                            "No rejection reason recorded."}
                        </div>
                      </div>
                    )}

                    {item.notes && (
                      <div className="history-notes">
                        <span>Engineer notes</span>
                        <p>{item.notes}</p>
                      </div>
                    )}

                    {item.recommendation && (
                      <div className="history-impact">
                        <div>
                          <span>
                            Predicted Oil Change
                          </span>
                          <strong>
                            {signedPct(
                              item.recommendation
                                .oil_change_pct
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Rod Risk Change
                          </span>
                          <strong>
                            {signedPct(
                              item.recommendation
                                .risk_change_pct
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Energy Change
                          </span>
                          <strong>
                            {signedPct(
                              item.recommendation
                                .energy_change_pct
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>Optimizer</span>
                          <strong>
                            {
                              item.recommendation
                                .optimizer_version
                            }
                          </strong>
                        </div>
                      </div>
                    )}

                    <div className="history-footer">
                      <span>
                        Decision ID #{item.decision_id}
                      </span>

                      {item.engineer_id ? (
                        <span>
                          Engineer:{" "}
                          {item.engineer_id}
                        </span>
                      ) : (
                        <span>
                          Engineer review
                        </span>
                      )}
                    </div>
                  </article>
                )
              )}
            </div>
          )}
        </section>
      </>
    );
  }

  function renderActiveSection() {
    switch (activeSection) {
      case "dashboard":
        return renderDashboard();

      case "digital-twin":
        return renderDigitalTwin();

      case "what-if":
        return renderWhatIf();

      case "optimization":
        return renderOptimization();

      case "review":
        return renderEngineerReview();

      case "history":
        return renderHistory();

      default:
        return renderDashboard();
    }
  }

  // ----------------------------------------------------------
  // Loading
  // ----------------------------------------------------------

  if (loadingWells) {
    return (
      <main className="app">
        <div className="status-screen">
          <h1>WellWise</h1>
          <p>Loading wells...</p>
        </div>
      </main>
    );
  }

  // ----------------------------------------------------------
  // Error before data
  // ----------------------------------------------------------

  if (error && !data) {
    return (
      <main className="app">
        <div className="status-screen">
          <h1>WellWise</h1>
          <p className="error">{error}</p>
          <p>
            Make sure FastAPI is running.
          </p>
        </div>
      </main>
    );
  }

  if (!data) {
    return null;
  }

  // ----------------------------------------------------------
  // Main application
  // ----------------------------------------------------------

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">W</div>

          <div>
            <strong>WellWise</strong>
            <span>
              Baghewala Digital Twin
            </span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map(
            ([section, label], index) => (
              <button
                key={section}
                type="button"
                className={
                  activeSection === section
                    ? "nav-item active"
                    : "nav-item"
                }
                onClick={() =>
                  changeSection(section)
                }
              >
                <span className="nav-number">
                  {String(index + 1).padStart(
                    2,
                    "0"
                  )}
                </span>
                <span>{label}</span>
              </button>
            )
          )}
        </nav>

        <button
          type="button"
          className="sidebar-status"
          onClick={() =>
            setShowSystemStatus(
              (current) => !current
            )
          }
        >
          <span className="status-dot" />

          <div>
            <strong>System Online</strong>
            <span>
              {systemHealthLoading
                ? "Checking system..."
                : "API · DB · Models Ready"}
            </span>
          </div>

          <span className="status-arrow">
            {showSystemStatus ? "↓" : "→"}
          </span>
        </button>

        {showSystemStatus && (
          <div className="system-status-panel">
            <div className="system-status-title">
              <strong>System Status</strong>

              <span>
                {systemHealthLoading
                  ? "CHECKING"
                  : systemHealth?.status === "ok"
                    ? "HEALTHY"
                    : "UNAVAILABLE"}
              </span>
            </div>

            <div className="system-status-row">
              <span>API</span>
              <strong>
                {systemHealthLoading
                  ? "CHECKING"
                  : systemHealth?.status === "ok"
                    ? "ONLINE"
                    : "OFFLINE"}
              </strong>
            </div>

            <div className="system-status-row">
              <span>Models</span>
              <strong>
                {systemHealthLoading
                  ? "CHECKING"
                  : systemHealth?.models_loaded
                    ? "READY"
                    : "NOT READY"}
              </strong>
            </div>

            <div className="system-status-row">
              <span>Optimizer</span>
              <strong>
                {systemHealthLoading
                  ? "CHECKING"
                  : systemHealth?.optimizer_loaded
                    ? "READY"
                    : "NOT READY"}
              </strong>
            </div>

            <div className="system-status-row">
              <span>Telemetry</span>
              <strong>
                {systemHealthLoading
                  ? "CHECKING"
                  : String(
                      systemHealth?.telemetry_source ??
                        "UNKNOWN"
                    )}
              </strong>
            </div>

            <div className="system-status-row">
              <span>Autonomous Control</span>
              <strong>DISABLED</strong>
            </div>
          </div>
        )}
      </aside>

      <main className="main-content">
        <div className="app">
          {renderTopBar()}
          {renderWellHeader()}

          {error && (
            <div className="inline-error">
              <span>{error}</span>

              <button
                type="button"
                onClick={() =>
                  setError(null)
                }
              >
                Dismiss
              </button>
            </div>
          )}

          {renderActiveSection()}

          <footer className="footer">
            <span>
              Last update:{" "}
              {formatDateTime(
                data.telemetry.timestamp
              )}
            </span>

            <span>
              Models: {data.system.models}
            </span>

            <span>
              Optimizer:{" "}
              {data.system.optimizer}
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default App;
