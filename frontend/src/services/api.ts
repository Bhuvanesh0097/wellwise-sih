const API_BASE_URL = "http://127.0.0.1:8000";

export interface DigitalTwinResponse {
  well: {
    well_id: string;
    field: string | null;
    reservoir: string | null;
    formation: string | null;
    status: string;
    api_gravity: number | null;
    asphaltene_content: number | null;
  };

  telemetry: {
    timestamp: string;
    source: string;
    reservoir_temperature: number;
    reservoir_pressure: number;
    oil_viscosity: number;
    oil_rate: number;
    water_rate: number;
    energy: number;
    fluid_level: number;
    spm: number;
    stroke_length: number;
    vfd_frequency: number;
    rod_load: number;
    pump_load: number;
    pump_fillage: number;
  };

  prediction_24h: {
    reservoir_temperature: number;
    oil_rate: number;
    rod_floating_probability: number;
    rod_floating_risk_pct: number;
    rod_status: string;
  };

  optimization: {
    status: string;
    candidate_count: number;
    feasible_candidates: number;

    baseline: {
      temperature: number;
      oil: number;
      risk: number;
      energy: number;
    };

    recommendation: {
      steam_rate: number;
      steam_temperature: number;
      injection_pressure: number;
      injection_duration: number;
      soak_time: number;
      steam_volume: number;
      stroke_length: number;
      spm: number;
      vfd_frequency: number;

      predicted_temperature: number;
      predicted_oil_rate: number;
      predicted_rod_risk: number;
      predicted_energy: number;
      sor_proxy: number;

      oil_change_pct: number;
      risk_change_pct: number;
      energy_change_pct: number;
      optimization_score: number;
    } | null;
  };

  system: {
    telemetry: string;
    models: string;
    optimizer: string;
    autonomous_control: boolean;
  };
}

export async function getDigitalTwin(
  wellId: string
): Promise<DigitalTwinResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/digital-twin/${wellId}`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch Digital Twin: ${response.status}`
    );
  }

  return response.json();
}
export interface Well {
  well_id: string;
  field_name: string | null;
  reservoir_name: string | null;
  formation_name: string | null;
  well_status: string;
  api_gravity: number | null;
  asphaltene_content: number | null;
}

export async function getWells(): Promise<Well[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/wells`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch wells: ${response.status}`
    );
  }

  return response.json();
}
export interface WhatIfRequest {
  steam_rate: number;
  steam_temperature: number;
  injection_pressure: number;
  injection_duration: number;
  soak_time: number;
  stroke_length: number;
  spm: number;
  vfd_frequency?: number;
}

export interface WhatIfResponse {
  well_id: string;
  timestamp: string;
  simulation_type: string;
  saved_to_database: boolean;

  baseline: {
    temperature: number;
    oil_rate: number;
    rod_risk_pct: number;
    energy: number;
  };

  scenario: {
    steam_rate: number;
    steam_temperature: number;
    injection_pressure: number;
    injection_duration: number;
    soak_time: number;
    steam_volume: number;
    stroke_length: number;
    spm: number;
    vfd_frequency: number;
  };

  predicted_outcome: {
    temperature: number;
    oil_rate: number;
    rod_risk_pct: number;
    rod_status: string;
    energy: number;
    sor_proxy: number;
  };

  changes_vs_baseline: {
    oil_change_pct: number;
    risk_change_pct: number;
    energy_change_pct: number;
  };
}

export async function runWhatIf(
  wellId: string,
  scenario: WhatIfRequest
): Promise<WhatIfResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/what-if/${wellId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(scenario),
    }
  );

  if (!response.ok) {
    let message = `What-If simulation failed: ${response.status}`;

    try {
      const errorData = await response.json();

      if (errorData.detail) {
        message = errorData.detail;
      }
    } catch {
      // Keep default error message
    }

    throw new Error(message);
  }

  return response.json();
}
export interface OptimizationResponse {
  well_id: string;
  status: string;
  timestamp: string;

  prediction_id: number;
  recommendation_id: number;

  baseline: {
    temperature: number;
    oil: number;
    risk: number;
    energy: number;
  };

  feasible_candidates: number;

  recommendation: {
    steam_rate: number;
    steam_temperature: number;
    injection_pressure: number;
    injection_duration: number;
    soak_time: number;
    steam_volume: number;
    stroke_length: number;
    spm: number;
    vfd_frequency: number;

    predicted_temperature: number;
    predicted_oil_rate: number;
    predicted_rod_risk: number;
    predicted_energy: number;
    sor_proxy: number;

    oil_change_pct: number;
    risk_change_pct: number;
    energy_change_pct: number;
    optimization_score: number;
  };
}

export async function getOptimization(
  wellId: string
): Promise<OptimizationResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/optimize/${wellId}`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch optimization: ${response.status}`
    );
  }

  return response.json();
}
export interface EngineerDecisionRequest {
  recommendation_id: number;
  decision: "APPROVE" | "MODIFY" | "REJECT";
  modified_parameters?: Record<string, number>;
  rejection_reason?: string;
  notes?: string;
}

export interface EngineerDecisionResponse {
  decision_id: number;
  well_id: string;
  recommendation_id: number;
  decision: "APPROVE" | "MODIFY" | "REJECT";
  modified_parameters: Record<string, number> | null;
  rejection_reason: string | null;
  notes: string | null;
  created_at?: string;

  modified_simulation?: {
    parameters: Record<string, number>;
    predicted_outcome: {
      temperature: number;
      oil_rate: number;
      rod_risk_pct: number;
      energy: number;
      sor_proxy: number;
    };
    changes_vs_baseline: {
      oil_change_pct: number;
      risk_change_pct: number;
      energy_change_pct: number;
    };
  } | null;
}
export async function submitEngineerDecision(
  wellId: string,
  request: EngineerDecisionRequest
): Promise<EngineerDecisionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/decisions/${wellId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      errorText || "Failed to submit engineer decision"
    );
  }

  return response.json();
}
export interface DecisionHistoryItem {
  decision_id: number;
  well_id: string;
  recommendation_id: number | null;
  engineer_id: string | null;
  decision: "APPROVE" | "MODIFY" | "REJECT";
  modified_parameters: Record<string, number> | null;
  rejection_reason: string | null;
  notes: string | null;
  created_at: string;
  recommendation: {
    id: number;
    well_id: string;
    prediction_id: number;
    created_at: string;

    steam_rate: number;
    steam_temperature: number;
    injection_pressure: number;
    injection_duration: number;
    soak_time: number;
    steam_volume: number;

    stroke_length: number;
    spm: number;
    vfd_frequency: number;

    predicted_reservoir_temperature: number;
    predicted_oil_rate: number;
    predicted_rod_risk_pct: number;
    predicted_energy: number;
    sor_proxy: number;

    optimization_score: number;
    oil_change_pct: number;
    risk_change_pct: number;
    energy_change_pct: number;

    optimizer_status: string;
    candidate_count: number;
    feasible_candidate_count: number;
    optimizer_version: string;
  } | null;
}

export interface DecisionHistoryResponse {
  well_id: string;
  count: number;
  history: DecisionHistoryItem[];
}

export async function getDecisionHistory(
  wellId: string
): Promise<DecisionHistoryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/decisions/history/${wellId}`
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      errorText || "Failed to load engineer decision history"
    );
  }

  return response.json();
}
export interface HistoricalTelemetry {
  id: number;
  well_id: string;
  timestamp: string;
  reservoir_temperature: number;
  reservoir_pressure: number;
  oil_rate: number;
  water_rate: number;
  energy: number;
  fluid_level: number;
  spm: number;
  stroke_length: number;
  vfd_frequency: number;
  rod_load: number;
  pump_load: number;
  pump_fillage: number;
}

export async function getTelemetryHistory(
  wellId: string,
  limit = 144
): Promise<HistoricalTelemetry[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/telemetry-history/${wellId}?limit=${limit}`
  );

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      errorText || "Failed to load telemetry history"
    );
  }

  const result = await response.json();

  return Array.isArray(result)
    ? result
    : result.telemetry ?? [];
}
export interface SystemHealth {
  status: string;
  message?: string;
  [key: string]: unknown;
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const response = await fetch(
    `${API_BASE_URL}/api/health`
  );

  if (!response.ok) {
    throw new Error(
      `Health check failed: ${response.status}`
    );
  }

  return (await response.json()) as SystemHealth;
}