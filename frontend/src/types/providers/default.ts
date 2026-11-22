/**
 * Default Provider Types
 *
 * Type definitions for the default provider management feature.
 */

/**
 * Default Provider Response
 */
export interface DefaultProviderResponse {
  provider_id: number;
  provider_name: string;
  provider_type: string;
  model_name: string;
  base_url: string | null;
  is_active: boolean;
}

/**
 * Set Default Provider Request
 */
export interface SetDefaultProviderRequest {
  provider_id: number;
  /** Optional: `PUT /providers/default` writes it to the row's `config.default_model`. */
  model?: string;
}

/**
 * Initialize Default Provider Response
 */
export interface InitializeDefaultProviderResponse {
  status: 'success' | 'warning';
  message: string;
  provider_id?: number;
  provider_name?: string;
  provider_type?: string;
}

/**
 * Provider Config with is_default field
 */
export interface ProviderConfigWithDefault {
  id: number;
  name: string;
  display_name: string | null;
  provider_type: string;
  base_url: string | null;
  is_active: boolean;
  priority: number;
  is_default: boolean;
  config: Record<string, unknown> | null;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Provider List Response with defaults
 */
export interface ProviderConfigListWithDefaultsResponse {
  providers: ProviderConfigWithDefault[];
  total: number;
}
