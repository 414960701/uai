# UAI Forge backend

The backend contains the Python runtime, plugin contracts, SQLite control-plane
storage, FastAPI API and run-event stream. It targets Python 3.9+ so it works on
older local environments while keeping the runtime fully asynchronous.

See the repository root README for setup and deployment instructions.

Provider credentials and model settings are managed through the single database-backed
`/api/v1/model-configs` endpoint. The curated provider/model catalog is available at
`/api/v1/model-catalog`. Configure `UAI_FORGE_CREDENTIAL_MASTER_KEY` from a secret manager
in deployed environments; it is a bootstrap value and is never stored in SQLite.
