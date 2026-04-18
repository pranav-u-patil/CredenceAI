"""
run.py — robust launcher for a FastAPI app served by Uvicorn.

Features:
- Windows Proactor event loop policy when needed
- Optional uvloop on Unix for better performance
- CLI / env var configuration for host, port, reload, log level
- Structured logging setup
- Graceful shutdown on SIGINT/SIGTERM
"""
from __future__ import annotations

import os
import sys
import signal
import argparse
import asyncio
import logging
from typing import Optional

# Windows: ensure ProactorEventLoop for subprocess/IO compatibility
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# Try to use uvloop on Unix for better throughput (optional)
if sys.platform != "win32":
    try:
        import uvloop  # type: ignore
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except Exception:
        pass

import uvicorn  # type: ignore

DEFAULT_HOST = os.getenv("APP_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("APP_PORT", "8000"))
DEFAULT_RELOAD = os.getenv("APP_RELOAD", "false").lower() in ("1", "true", "yes")
DEFAULT_LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "info")


def configure_logging(level: str) -> None:
    lvl_name = level.upper()
    # basicConfig accepts level as int or str name
    logging.basicConfig(
        level=lvl_name,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # set uvicorn loggers to same level
    try:
        logging.getLogger("uvicorn.error").setLevel(lvl_name)
        logging.getLogger("uvicorn.access").setLevel(lvl_name)
    except Exception:
        # ignore if uvicorn loggers not present yet
        pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Uvicorn server for app.main:app")
    p.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    p.add_argument(
        "--reload",
        action="store_true",
        default=DEFAULT_RELOAD,
        help="Enable autoreload (dev only)",
    )
    p.add_argument("--log-level", default=DEFAULT_LOG_LEVEL, help="Logging level")
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (use Gunicorn for >1)",
    )
    p.add_argument("--app", default="main:app", help="ASGI app import path")
    return p.parse_args()


async def _run_uvicorn(config: uvicorn.Config, stop_event: asyncio.Event) -> None:
    """
    Run uvicorn.Server.serve() and return when server stops or stop_event is set.
    """
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())

    # Wait for either server to finish or external stop_event
    done, pending = await asyncio.wait(
        {serve_task, asyncio.create_task(stop_event.wait())},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # If stop_event triggered, request server shutdown
    if not serve_task.done():
        server.should_exit = True
        try:
            await serve_task
        except asyncio.CancelledError:
            pass


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    logger = logging.getLogger("run")

    if args.workers != 1:
        logger.warning(
            "Using multiple workers from this script is not recommended. "
            "Use Gunicorn with uvicorn.workers.UvicornWorker for production."
        )

    logger.info(
        f"Starting server host={args.host} port={args.port} reload={args.reload} app={args.app}"
    )

    config = uvicorn.Config(
        app=args.app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )

    # Use asyncio.run for a clean event loop lifecycle
    async def _main() -> None:
        stop_event = asyncio.Event()

        def _signal_handler(signum: int, frame: Optional[object]) -> None:
            logger.info(f"Received signal to stop: {signum}")
            # schedule stop in event loop
            try:
                # set the event in a thread-safe manner
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                # fallback if no running loop
                try:
                    stop_event.set()
                except Exception:
                    pass

        # Register signals (best-effort)
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _signal_handler)
            except Exception:
                # Some platforms may not allow setting all signals
                pass

        # Run uvicorn server and wait for stop_event
        try:
            await _run_uvicorn(config, stop_event)
        except Exception as exc:
            logger.exception("Uvicorn server raised an exception", exc_info=exc)
        finally:
            logger.info("Server shutdown complete")

    try:
        asyncio.run(_main())
    except Exception as e:
        logger.exception("Server crashed", exc_info=e)
    finally:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
