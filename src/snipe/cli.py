"""SNIPE CLI - Command Line Interface."""

import json as json_lib
from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from snipe.config import load_config
from snipe.database import init_db, get_db

console = Console()


@click.group()
@click.version_option(package_name="snipe")
def cli():
    """SNIPE Stock Scanner - Scan, Narrow, Inspect, Position, Execute.

    A systematic stock scanning tool implementing the SNIPE framework
    for Indian NSE stocks (Nifty 500 universe).
    """
    pass


@cli.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--equity", default=1000000, help="Account equity (default 10L)")
def scan(output_json, equity):
    """Run full SNIPE pipeline and display watchlist."""
    from snipe.pipeline import run_pipeline
    from snipe.scoring.regime import classify_regime, compute_breadth, assess_index_trend
    from snipe.data.fii_dii import compute_rolling_fii_flow

    config = load_config()

    if not output_json:
        console.print("[bold blue]SNIPE Scan[/bold blue] - Running full pipeline...")

    # Determine regime first
    # For now, default to "green" — full regime detection requires loaded data
    regime = "green"

    def progress(stage, count):
        if not output_json:
            console.print(f"  Stage: {stage} → {count} stocks", style="dim")

    try:
        result = run_pipeline(
            account_equity=equity,
            regime=regime,
            config=config,
            progress_callback=progress,
        )
    except Exception as e:
        if output_json:
            click.echo(json_lib.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error running pipeline:[/red] {e}")
            console.print("Make sure you have loaded data first. Run: snipe fetch")
        return

    if output_json:
        click.echo(json_lib.dumps(result, indent=2, default=str))
        return

    # Display stage counts
    counts = result["stage_counts"]
    console.print(Panel(
        f"Universe: {counts.get('universe', 0)} → "
        f"TT Pass: {counts.get('trend_template', 0)} → "
        f"Patterns: {counts.get('pattern_detection', 0)} → "
        f"Fundamentals: {counts.get('fundamental_screen', 0)} → "
        f"[bold]Watchlist: {counts.get('final_watchlist', 0)}[/bold]",
        title="Pipeline Stages",
    ))

    # Display watchlist
    watchlist = result.get("watchlist", [])
    if not watchlist:
        console.print("[yellow]No candidates found matching all criteria.[/yellow]")
        return

    table = Table(title=f"SNIPE Watchlist - {result['scan_date']}")
    table.add_column("#", style="bold")
    table.add_column("Symbol", style="cyan")
    table.add_column("Sector")
    table.add_column("Price", justify="right")
    table.add_column("Pivot", justify="right")
    table.add_column("Stop", justify="right")
    table.add_column("Score", justify="right", style="green")
    table.add_column("Edges", justify="right")
    table.add_column("TT", justify="right")
    table.add_column("VCP", justify="right")
    table.add_column("CANSLIM", justify="right")

    for item in watchlist:
        table.add_row(
            str(item.get("rank", "")),
            item["symbol"],
            item.get("sector", "")[:12],
            f"{item.get('current_price', 0):.0f}",
            f"{item.get('pivot_price', 0):.0f}",
            f"{item.get('stop_price', 0):.0f}",
            f"{item.get('composite_score', 0):.0f}",
            str(item.get("edge_count", 0)),
            f"{item.get('trend_template_score', 0)}/10",
            f"{item.get('vcp_quality', 0):.0f}",
            f"{item.get('canslim_score', 0)}/7",
        )

    console.print(table)


@cli.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def regime(output_json):
    """Show current market regime (GREEN/YELLOW/RED)."""
    from snipe.scoring.regime import classify_regime, assess_index_trend
    from snipe.data.fii_dii import compute_rolling_fii_flow

    if not output_json:
        console.print("[bold blue]Market Regime Assessment[/bold blue]")

    fii_flow = compute_rolling_fii_flow()

    # Simplified regime output (full requires loaded breadth data)
    result = {
        "fii_flow": fii_flow,
        "note": "Full regime requires loaded price data for breadth calculation. Run 'snipe fetch' first.",
    }

    if output_json:
        click.echo(json_lib.dumps(result, indent=2, default=str))
        return

    console.print(f"FII 5-day net: {fii_flow.get('fii_net_5d', 'N/A')}")
    console.print(f"FII 20-day net: {fii_flow.get('fii_net_20d', 'N/A')}")
    console.print(f"FII status: {fii_flow.get('fii_flow_status', 'N/A')}")


@cli.command()
@click.argument("symbol")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def inspect(symbol, output_json):
    """Deep-dive analysis of a single stock."""
    from snipe.data.prices import get_stock_prices, fetch_stock_prices, store_prices
    from snipe.scanning.trend_template import check_trend_template
    from snipe.scanning.vcp import detect_vcp
    from snipe.scanning.stage_analysis import classify_stage
    from snipe.scanning.breakout import detect_breakout

    config = load_config()
    symbol = symbol.upper()

    if not output_json:
        console.print(f"[bold blue]Inspecting: {symbol}[/bold blue]")

    # Try to get from DB first, then fetch live
    df = get_stock_prices(symbol)
    if df.empty:
        if not output_json:
            console.print("Fetching live data...", style="dim")
        df = fetch_stock_prices(symbol)
        if df.empty:
            if output_json:
                click.echo(json_lib.dumps({"error": f"No data available for {symbol}"}))
            else:
                console.print(f"[red]No data available for {symbol}[/red]")
            return
        store_prices(df)

    # Run all analyses
    tt_result = check_trend_template(df, rs_percentile=50.0, config=config)
    vcp_result = detect_vcp(df, config)
    stage_result = classify_stage(df, config)

    pivot = vcp_result.get("pivot_price", 0) or df["high"].astype(float).tail(252).max()
    bo_result = detect_breakout(df, pivot, config)

    result = {
        "symbol": symbol,
        "current_price": float(df["close"].iloc[-1]),
        "trend_template": tt_result,
        "vcp": vcp_result,
        "stage": stage_result,
        "breakout": bo_result,
    }

    if output_json:
        click.echo(json_lib.dumps(result, indent=2, default=str))
        return

    # Display rich output
    console.print(Panel(f"Price: {result['current_price']:.2f}", title=symbol))

    # Trend Template
    tt = tt_result
    tt_color = "green" if tt["trend_template_pass"] else "red"
    console.print(f"Trend Template: [{tt_color}]{tt['score']}/10[/{tt_color}]")
    for k, v in tt["criteria"].items():
        icon = "[green]✓[/green]" if v else "[red]✗[/red]"
        console.print(f"  {icon} {k}")

    # VCP
    vcp = vcp_result
    if vcp["vcp_detected"]:
        console.print(f"\nVCP: [green]Detected[/green] ({vcp['contractions']} contractions)")
        console.print(f"  Depths: {vcp['depths']}")
        console.print(f"  Pivot: {vcp['pivot_price']:.2f}")
        console.print(f"  Quality: {vcp['vcp_quality']} ({vcp['quality_score']:.1f}/10)")
    else:
        console.print("\nVCP: [dim]Not detected[/dim]")

    # Stage
    console.print(f"\nStage: {stage_result['stage']} (confirmed: {stage_result['stage_confirmed']})")
    console.print(f"  Duration: {stage_result['stage_duration_weeks']} weeks")

    # Breakout
    bo = bo_result
    if bo["breakout_detected"]:
        console.print(f"\nBreakout: [green]YES[/green] ({bo['breakout_strength']})")
        console.print(f"  Volume ratio: {bo['volume_ratio']:.1f}x")
        console.print(f"  HV1: {bo['hv1_edge']}, HVE: {bo['hve_edge']}")
    elif bo["approaching_breakout"]:
        console.print(f"\nBreakout: [yellow]Approaching[/yellow] ({bo['distance_to_pivot_pct']:.1f}% away)")
    else:
        console.print(f"\nBreakout: [dim]Not yet[/dim] ({bo['distance_to_pivot_pct']:.1f}% from pivot)")


@cli.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def positions(output_json):
    """Show open positions with P&L and sell signals."""
    from snipe.signals.sell_rules import compute_position_status, check_defensive_signals, check_offensive_signals
    from snipe.data.prices import get_stock_prices

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM positions WHERE status = 'open'"
    ).fetchall()
    conn.close()

    if not rows:
        console.print("[dim]No open positions.[/dim]")
        return

    results = []
    for row in rows:
        row_dict = dict(row)
        symbol = row_dict["symbol"]
        df = get_stock_prices(symbol, days=50)

        if not df.empty:
            current_price = float(df["close"].iloc[-1])
            status = compute_position_status(
                row_dict["entry_price"], row_dict["stop_price"],
                current_price, row_dict["entry_date"]
            )

            # Check signals
            defensive = check_defensive_signals(
                df, row_dict["entry_price"], row_dict["stop_price"]
            )
            offensive = check_offensive_signals(
                df, row_dict["entry_price"],
                status["gain_pct"], status["days_held"]
            )

            results.append({
                **row_dict,
                **status,
                "signals": defensive + offensive,
            })

    if output_json:
        click.echo(json_lib.dumps(results, indent=2, default=str))
        return

    table = Table(title="Open Positions")
    table.add_column("Symbol", style="cyan")
    table.add_column("Entry", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Gain%", justify="right")
    table.add_column("R-Mult", justify="right")
    table.add_column("Days", justify="right")
    table.add_column("Signals")

    for r in results:
        gain_color = "green" if r["gain_pct"] > 0 else "red"
        signal_text = ", ".join(s["type"] for s in r.get("signals", []))
        table.add_row(
            r["symbol"],
            f"{r['entry_price']:.0f}",
            f"{r['current_price']:.0f}",
            f"[{gain_color}]{r['gain_pct']:.1f}%[/{gain_color}]",
            f"{r['r_multiple']:.1f}R",
            str(r["days_held"]),
            signal_text or "-",
        )

    console.print(table)


@cli.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def history(output_json):
    """Show historical scan results and trade outcomes."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM watchlist_history ORDER BY scan_date DESC, rank ASC LIMIT 50"
    ).fetchall()
    conn.close()

    if not rows:
        console.print("[dim]No scan history yet. Run 'snipe scan' to generate watchlists.[/dim]")
        return

    results = [dict(r) for r in rows]

    if output_json:
        click.echo(json_lib.dumps(results, indent=2, default=str))
        return

    table = Table(title="Watchlist History (Last 50 entries)")
    table.add_column("Date")
    table.add_column("#", style="bold")
    table.add_column("Symbol", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Entry?")
    table.add_column("Outcome")

    for r in results:
        table.add_row(
            r["scan_date"],
            str(r["rank"]),
            r["symbol"],
            f"{r.get('composite_score', 0):.0f}",
            "Yes" if r.get("entry_triggered") else "-",
            r.get("outcome", "-"),
        )

    console.print(table)


@cli.command()
@click.option("--symbols", default=5, help="Number of stocks to fetch (for testing)")
def fetch(symbols):
    """Fetch price data for the universe (or a test subset)."""
    from snipe.data.universe import refresh_universe, get_universe
    from snipe.data.prices import fetch_and_store_prices

    config = load_config()

    console.print("[bold blue]Fetching data...[/bold blue]")

    # Refresh universe
    console.print("Refreshing Nifty 500 universe...", style="dim")
    try:
        count = refresh_universe()
        console.print(f"  Universe: {count} stocks")
    except Exception as e:
        console.print(f"  [yellow]Universe fetch failed: {e}. Using cached if available.[/yellow]")

    # Fetch prices for top N stocks (or all if --symbols=500)
    universe = get_universe()
    fetch_list = [s["symbol"] for s in universe[:symbols]]

    console.print(f"Fetching 1-year prices for {len(fetch_list)} stocks...")

    def progress(symbol, i, total):
        if i % 10 == 0 or i == total:
            console.print(f"  [{i}/{total}] {symbol}", style="dim")

    result = fetch_and_store_prices(fetch_list, progress_callback=progress)
    console.print(f"  Done: {result['success']} success, {result['failed']} failed, {result['total_rows']} rows")
