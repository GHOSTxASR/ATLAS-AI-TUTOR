import { useEffect, useState } from "react";
import {
  Check,
  ExternalLink,
  Eye,
  EyeOff,
  Key,
  Loader2,
  Settings,
  Sparkles,
  Zap,
  Moon,
  Sun,
  Laptop,
  Palette,
  ShieldCheck,
  Trash2,
  ChevronDown,
} from "lucide-react";
import { apiClient } from "../api/client";
import { settingsApi, ProvidersData, ModelInfo } from "../api/settings";
import { ModelPicker } from "../components/settings/ModelPicker";
import { useThemeStore, ThemeMode } from "../stores/themeStore";
import { Skeleton, CardSkeleton } from "../components/common/LoadingStates";

export function SettingsPage() {
  const { theme, resolvedTheme, setTheme } = useThemeStore();

  const [providersData, setProvidersData] = useState<ProvidersData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form state
  const [selectedProvider, setSelectedProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("");
  const [showKey, setShowKey] = useState(false);

  // Model catalog, fetched live from the provider
  const [modelCatalog, setModelCatalog] = useState<ModelInfo[]>([]);
  const [catalogSource, setCatalogSource] = useState<"live" | "fallback">("fallback");
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);

  // Embedding model: a separate catalogue, and changing it invalidates the
  // vector index, so the indexed model is tracked alongside.
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [embeddingCatalog, setEmbeddingCatalog] = useState<ModelInfo[]>([]);
  const [embeddingSource, setEmbeddingSource] = useState<"live" | "fallback">("fallback");
  const [embeddingError, setEmbeddingError] = useState<string | null>(null);
  const [indexedModels, setIndexedModels] = useState<string[]>([]);
  const [loadingEmbeddings, setLoadingEmbeddings] = useState(false);

  useEffect(() => {
    loadProviders();
  }, []);

  const loadModels = async (provider: string, refresh = false) => {
    if (!provider) return;
    setLoadingModels(true);
    try {
      const data = await settingsApi.getModels(provider, refresh);
      setModelCatalog(data.models ?? []);
      setCatalogSource(data.source ?? "fallback");
      setCatalogError(data.error ?? null);
    } catch {
      setModelCatalog([]);
      setCatalogSource("fallback");
      setCatalogError("Could not reach the server.");
    } finally {
      setLoadingModels(false);
    }
  };

  const loadEmbeddingModels = async (provider: string, refresh = false) => {
    if (!provider) return;
    setLoadingEmbeddings(true);
    try {
      const data = await settingsApi.getEmbeddingModels(provider, refresh);
      setEmbeddingCatalog(data.models ?? []);
      setEmbeddingSource(data.source ?? "fallback");
      setEmbeddingError(data.error ?? null);
      setIndexedModels(data.indexed_models ?? []);
      setEmbeddingModel((current) => current || data.active_model || "");
    } catch {
      setEmbeddingCatalog([]);
      setEmbeddingSource("fallback");
      setEmbeddingError("Could not reach the server.");
    } finally {
      setLoadingEmbeddings(false);
    }
  };

  // Re-query whenever the provider changes; lists go stale on their own.
  useEffect(() => {
    loadModels(selectedProvider);
    setEmbeddingModel("");
    loadEmbeddingModels(selectedProvider);
  }, [selectedProvider]);

  const loadProviders = async () => {
    setLoading(true);
    try {
      const data = await settingsApi.getProviders();
      setProvidersData(data);
      setSelectedProvider(data.active_provider);
      setModelName(data.active_model);
    } catch (err: any) {
      setError("Failed to load providers");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const data = await settingsApi.setProvider({
        provider: selectedProvider,
        api_key: apiKey,
        model: modelName,
        embedding_model: embeddingModel,
      });
      setSuccess(data.message);
      setApiKey("");
      await loadProviders();
      await loadEmbeddingModels(selectedProvider, true);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setError(null);
    setSuccess(null);
    setTestResult(null);
    try {
      const result = await settingsApi.testConnection(selectedProvider);
      setTestResult(
        result.status === "ok"
          ? {
              ok: true,
              message: `Connected to ${result.model_info?.model ?? selectedProvider}.`,
            }
          : { ok: false, message: result.error || "Connection failed." }
      );
    } catch (err: any) {
      setTestResult({
        ok: false,
        message: err.response?.data?.error?.message || "Connection test failed.",
      });
    } finally {
      setTesting(false);
    }
  };

  const handleDeleteKey = async () => {
    if (!activeProviderInfo) return;
    const confirmed = window.confirm(
      `Remove the stored ${activeProviderInfo.label} API key? You will need to re-enter it to use this provider.`
    );
    if (!confirmed) return;

    setError(null);
    setSuccess(null);
    setTestResult(null);
    try {
      await settingsApi.deleteApiKey(activeProviderInfo.id);
      setSuccess(`Removed the stored ${activeProviderInfo.label} API key.`);
      await loadProviders();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to remove the API key.");
    }
  };

  const activeProviderInfo = providersData?.providers.find(
    (p) => p.id === selectedProvider
  );

  return (
    <div className="w-full min-w-0 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-primary-container/30 text-primary border border-glass-border uppercase tracking-widest">
            Preferences & Telemetry
          </span>
        </div>
        <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1.5 tracking-tight">
          System Settings
        </h1>
        <p className="text-xs sm:text-sm text-on-surface-variant mt-1 font-sans">
          Configure local AI model backends, API key encryptions, and Liquid Glass workspace themes.
        </p>
      </div>

      {/* Theme Customization Section */}
      <div className="glass-panel p-6 rounded-2xl border border-glass-border space-y-4 shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <div className="flex items-center gap-2">
          <Palette className="w-5 h-5 text-primary" />
          <h2 className="font-editorial text-2xl text-on-surface">Workspace Appearance</h2>
        </div>
        <p className="text-xs text-on-surface-variant font-sans">
          Choose your visual appearance mode for the liquid glass environment:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-sans text-xs">
          {[
            { id: "light", label: "Light", icon: Sun, desc: "Frost Off-White" },
            { id: "dark", label: "Dark", icon: Moon, desc: "Ebony Slate" },
            { id: "system", label: "System", icon: Laptop, desc: "Auto OS Sync" },
          ].map((mode) => {
            const Icon = mode.icon;
            const isSelected = theme === mode.id;
            return (
              <button
                key={mode.id}
                onClick={() => setTheme(mode.id as ThemeMode)}
                className={`p-3 sm:p-4 rounded-xl border flex flex-col items-center justify-center gap-2 text-center transition ${
                  isSelected
                    ? "bg-surface-container/70 border-primary text-primary shadow-[0_0_10px_rgba(160,240,237,0.2)] luminous-active"
                    : "bg-surface-container/30 border-glass-border hover:bg-surface-container/60 text-on-surface-variant"
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="font-semibold text-xs text-on-surface">{mode.label}</span>
                <span className="text-[10px] leading-tight text-on-surface-variant">{mode.desc}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* AI Model Provider Configuration */}
      <div className="glass-panel p-6 rounded-2xl border border-glass-border space-y-5 shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary" />
          <h2 className="font-editorial text-2xl text-on-surface">AI Model Provider</h2>
        </div>
        <p className="text-xs text-on-surface-variant font-sans">
          Select your inference provider. API keys are encrypted at rest using AES-GCM Fernet tokens.
        </p>

        {loading ? (
          <CardSkeleton count={3} />
        ) : (
          <div className="space-y-4 font-sans text-xs">
            {/* Provider Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {providersData?.providers.map((p) => {
                const isSelected = selectedProvider === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setSelectedProvider(p.id);
                      setModelName(p.default_model);
                    }}
                    className={`p-3.5 rounded-xl border text-left flex flex-col justify-between space-y-2 transition ${
                      isSelected
                        ? "bg-surface-container/70 border-primary shadow-[0_0_10px_rgba(160,240,237,0.2)] luminous-active"
                        : "bg-surface-container/30 border-glass-border hover:bg-surface-container/60"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-xs text-on-surface">{p.label}</span>
                      {/* "Configured" previously covered two unrelated states:
                          a key you saved, and a provider that needs no key at
                          all (Ollama), which therefore always looked ready
                          even when it was not installed. */}
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        {p.active && (
                          <span className="text-[9px] font-mono uppercase bg-primary/20 text-primary border border-primary/30 px-1.5 py-0.5 rounded">
                            In use
                          </span>
                        )}
                        {p.env_key === "" ? (
                          <span className="text-[9px] font-mono uppercase bg-surface-container-high/60 text-on-surface-variant border border-glass-border px-1.5 py-0.5 rounded">
                            No key needed
                          </span>
                        ) : (
                          p.key_set && (
                            <span className="text-[9px] font-mono uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-1.5 py-0.5 rounded">
                              Key saved
                            </span>
                          )
                        )}
                      </div>
                    </div>
                    <span className="text-[10px] text-on-surface-variant font-mono">
                      Default: {p.default_model}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Provider Fields */}
            {activeProviderInfo && (
              <div className="space-y-3 pt-3 border-t border-glass-border">
                {activeProviderInfo.env_key && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-on-surface-variant font-semibold">
                        API Key ({activeProviderInfo.env_key})
                      </label>
                      <div className="flex items-center gap-2">
                        {activeProviderInfo.docs_url && (
                          <a
                            href={activeProviderInfo.docs_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-[10px] text-primary hover:underline"
                          >
                            <ExternalLink className="w-3 h-3" />
                            Get a key
                          </a>
                        )}
                        {activeProviderInfo.key_set && (
                          <button
                            type="button"
                            onClick={handleDeleteKey}
                            className="flex items-center gap-1 text-[10px] text-rose-400 hover:underline"
                          >
                            <Trash2 className="w-3 h-3" />
                            Remove key
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="relative">
                      <input
                        type={showKey ? "text" : "password"}
                        placeholder={activeProviderInfo.key_set ? "•••••••••••••••• (Encrypted in Keystore)" : "Enter API key..."}
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        className="w-full pl-3 pr-10 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                      />
                      <button
                        type="button"
                        onClick={() => setShowKey(!showKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface"
                      >
                        {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-on-surface-variant mb-1 font-semibold">
                    Model Name
                  </label>
                  {/* Searchable live list; typing is manual entry, so a model
                      the provider added today still works. */}
                  <ModelPicker
                    value={modelName}
                    onChange={setModelName}
                    models={modelCatalog}
                    source={catalogSource}
                    error={catalogError}
                    loading={loadingModels}
                    onRefresh={() => loadModels(selectedProvider, true)}
                  />
                </div>

                {/* Embedding model. Separate catalogue, and separate stakes:
                    switching it starts a new vector index rather than
                    reinterpreting the old one. */}
                <div>
                  <label className="block text-on-surface-variant mb-1 font-semibold">
                    Embedding Model
                    <span className="ml-1.5 font-normal text-on-surface-variant/70">
                      — used to index documents for search
                    </span>
                  </label>

                  {embeddingCatalog.length === 0 && embeddingError ? (
                    <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-200 text-[11px] leading-relaxed">
                      {embeddingError}
                      <span className="block mt-1 opacity-80">
                        Chat still works. Document search needs a provider with an
                        embeddings API — OpenAI, Gemini, Mistral, Together, or a local
                        Ollama model.
                      </span>
                    </div>
                  ) : (
                    <ModelPicker
                      value={embeddingModel}
                      onChange={setEmbeddingModel}
                      models={embeddingCatalog}
                      source={embeddingSource}
                      error={embeddingError}
                      loading={loadingEmbeddings}
                      onRefresh={() => loadEmbeddingModels(selectedProvider, true)}
                    />
                  )}

                  {indexedModels.length > 0 &&
                    embeddingModel &&
                    !indexedModels.includes(embeddingModel) && (
                      <div className="mt-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-200 text-[11px] leading-relaxed">
                        Your documents are indexed with{" "}
                        <span className="font-mono">{indexedModels.join(", ")}</span>.
                        Switching to <span className="font-mono">{embeddingModel}</span>{" "}
                        starts a new index — existing documents stay on disk but will not
                        be searchable until you reprocess them from the Library.
                      </div>
                    )}
                </div>
              </div>
            )}

            {error && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                {error}
              </div>
            )}

            {success && (
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs">
                {success}
              </div>
            )}

            {testResult && (
              <div
                className={`p-3 rounded-lg border text-xs flex items-start gap-2 ${
                  testResult.ok
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                    : "bg-rose-500/10 border-rose-500/20 text-rose-300"
                }`}
              >
                {testResult.ok ? (
                  <ShieldCheck className="w-4 h-4 shrink-0 mt-px" />
                ) : (
                  <Zap className="w-4 h-4 shrink-0 mt-px" />
                )}
                <span>{testResult.message}</span>
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 py-2.5 bg-primary hover:opacity-90 disabled:opacity-40 text-on-primary text-xs font-semibold rounded-xl shadow-[0_0_12px_rgba(160,240,237,0.25)] transition flex items-center justify-center gap-2"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                <span>{saving ? "Saving Configuration..." : "Save Settings"}</span>
              </button>

              <button
                onClick={handleTestConnection}
                disabled={testing || !selectedProvider}
                className="flex-1 py-2.5 bg-surface-container/60 hover:bg-surface-container border border-glass-border disabled:opacity-40 text-on-surface text-xs font-semibold rounded-xl transition flex items-center justify-center gap-2"
                title="Send a minimal request to verify the key and model work"
              >
                {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                <span>{testing ? "Testing..." : "Test Connection"}</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
