# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the application

```bash
# Start locally
python run.py

# On the Raspberry Pi (systemd service)
sudo systemctl start craftbeerpi
sudo systemctl status craftbeerpi
sudo journalctl -u craftbeerpi -f
```

The app runs on port 5000. The RPi is at `10.19.1.239` (user: `otavio`, pass: `123`).

## Deploying to the RPi

The plugin directories are root-owned, so direct `scp` won't work. Always use:

```bash
scp <file> otavio@10.19.1.239:/tmp/
ssh otavio@10.19.1.239 "echo '123' | sudo -S cp /tmp/<file> /home/otavio/craftbeerpi3/<destination>"
ssh otavio@10.19.1.239 "sudo systemctl restart craftbeerpi"
```

## Architecture

### Startup sequence

`run.py` → `modules/app_config.py` (creates `app`, `socketio`, `cbpi`) → `modules/__init__.py` (imports all modules, runs `init_db()`, `initPlugins()`, `cbpi.run_init()`, `cbpi.run_background_processes()`).

### Central object: `cbpi`

`CraftBeerPi` instance in `modules/core/core.py`. All runtime state lives in `cbpi.cache` (a plain dict). Decorator-based plugin registration:

| Decorator | Registers |
|-----------|-----------|
| `@cbpi.actor` | Actor type |
| `@cbpi.sensor` | Sensor type |
| `@cbpi.step` | Step type |
| `@cbpi.controller` | Kettle controller |
| `@cbpi.initalizer(order=N)` | Startup hook |
| `@cbpi.backgroundtask` | Background greenlet |

### Plugin directories

- `modules/base_plugins/` — always loaded at startup
- `modules/plugins/` — optional, loaded by `initPlugins()`

### Step execution

`StepBase(Timer, ActorAPI, SensorAPI, KettleAPI)` in `modules/core/step.py`. Steps run via `socketio.start_background_task`. Timer state (`timer_end`) is **persisted in SQLite** via `Property.Number("TIMER_END", configurable=False)` — always call `self.stop_timer()` as the first line of `init()` to clear stale values from previous runs, or steps will complete instantly on restart.

### Frontend

The UI is a minified React+Redux bundle at `modules/ui/static/bundle.js`. Socket.IO is non-functional (EIO v3/v4 mismatch with Flask-SocketIO 5); a REST polling workaround was added that calls `/api/sensor/`, `/api/step/`, `/api/kettle/`, `/api/actor/` every 2 seconds.

## Python 3 / Flask 3 compatibility notes

This fork targets Python 3.13 / Flask 3. Key changes from upstream:

- `RPi.GPIO` replaced by `rpi-lgpio 0.6` (drop-in, same API)
- `flask-classful` removed; blueprints used directly
- `flask_ask` (AmazonAlexaPlugin) replaced by `flask-ask-sdk` + `ask-sdk-core`; install with `--break-system-packages` on Raspbian (PEP 668 externally-managed env)
- DS18B20 sensor reads run in an OS thread via `eventlet.tpool.execute` to avoid blocking the event loop

## Logs

| File | Contents |
|------|----------|
| `logs/app.log` | General application log |
| `logs/action.log` | Step transitions (CSV) |
| `logs/step_events.log` | Detailed step events (STEP_START, TIMER_START, STEP_COMPLETE) |
| `logs/sensor_N.log` | Per-sensor temperature history |
| `logs/kettle_N.log` | Per-kettle temperature history |

## Plugins monorepo

Optional plugins for Python 3 are maintained at `luisgneiting/craftbeerpi3-plugins-py3` (branch: main). To install on the RPi:

```bash
cd /home/otavio/craftbeerpi3/modules
git clone https://github.com/luisgneiting/craftbeerpi3-plugins-py3 plugins
```
