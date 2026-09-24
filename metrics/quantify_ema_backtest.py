"""
EMA 股价预测精度回测脚本（无需 API Key，纯本地运行）

用途：忠实复现项目中的指数移动平均(EMA)预测逻辑，对 3 只股票做滚动回测，
      产出预测精度量化指标（MAE / RMSE / MAPE / 方向准确率）。

复现逻辑（对应 function_handler.exponential_moving_average 与 stock server）：
  - 平滑因子 alpha = 0.8
  - 用截至 t 日的历史收盘价计算 EMA，取最后一个 EMA 值作为对未来收盘价的预测

运行：python3 quantify_ema_backtest.py
输出：ema_backtest_results.json + 控制台汇总
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
STOCK_DATA_PATH = ROOT / "project1_stock_counselor" / "stock_data.xlsx"

ALPHA = 0.8          # 与项目代码一致
MIN_TRAIN = 20       # 最少历史窗口
HORIZONS = [1, 7]    # 预测步长：1 天 & 7 天


def ema_last(series: pd.Series, alpha: float = ALPHA):
    """计算序列的 EMA，返回最后一个 EMA 值（即项目对未来的预测值）。"""
    ema = series.ewm(alpha=alpha, adjust=False).mean()
    return float(ema.iloc[-1])


def backtest(close: np.ndarray, horizon: int = 1):
    """
    滚动回测：用截至 t 的历史数据预测 t+horizon-1（多步时以最后 EMA 值作为常数外推）。
    返回实际值与预测值数组。
    """
    actuals, preds = [], []
    n = len(close)
    # t 表示历史窗口的结束位置（不含），预测目标为 close[t+horizon-1]
    for t in range(MIN_TRAIN, n - horizon + 1):
        hist = pd.Series(close[:t])
        pred = ema_last(hist, ALPHA)
        actual = close[t + horizon - 1]
        actuals.append(float(actual))
        preds.append(pred)
    return np.array(actuals), np.array(preds)


def compute_metrics(actuals: np.ndarray, preds: np.ndarray, close: np.ndarray, horizon: int):
    """计算 MAE / RMSE / MAPE / 方向准确率。"""
    mae = float(np.mean(np.abs(actuals - preds)))
    rmse = float(np.sqrt(np.mean((actuals - preds) ** 2)))
    # MAPE：避免除以 0（收盘价不可能为 0，此处仅防御）
    with np.errstate(divide="ignore", invalid="ignore"):
        mape = float(np.nanmean(np.abs((actuals - preds) / actuals)) * 100)

    # 方向准确率：预测相对"上一实际值"的涨跌方向是否与真实一致
    # 对多步外推，使用目标日期的前一个真实值作为比较基准
    if horizon == 1:
        prev = close[MIN_TRAIN - 1: len(actuals) + MIN_TRAIN - 1]
        base = prev
        actual_prev = prev
    else:
        # 多步：比较相邻目标期方向意义有限，这里用最后历史值 close[t-1]
        base = np.array([close[t - 1] for t in range(MIN_TRAIN, len(close) - horizon + 1)])
        actual_prev = base

    pred_dir = np.sign(preds - base)
    actual_dir = np.sign(actuals - base)
    # 忽略方向为 0（持平）的样本
    mask = (actual_dir != 0)
    dir_acc = float(np.mean(pred_dir[mask] == actual_dir[mask]) * 100) if mask.any() else np.nan

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape_pct": round(mape, 2),
        "direction_accuracy_pct": round(dir_acc, 2) if not np.isnan(dir_acc) else None,
        "samples": int(len(actuals)),
    }


def main():
    xl = pd.ExcelFile(STOCK_DATA_PATH)
    per_stock = {}
    summary = {}

    for sheet in xl.sheet_names:
        df = pd.read_excel(STOCK_DATA_PATH, sheet_name=sheet, parse_dates=["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        close = df["Close"].to_numpy(dtype=float)

        stock_result = {"n_days": int(len(close))}
        for h in HORIZONS:
            actuals, preds = backtest(close, horizon=h)
            stock_result[f"h{h}"] = compute_metrics(actuals, preds, close, horizon=h)

        per_stock[sheet] = stock_result
        # 1 步 MAPE 与方向准确率用于汇总
        summary[sheet] = {
            "mape_pct_h1": stock_result["h1"]["mape_pct"],
            "direction_accuracy_pct_h1": stock_result["h1"]["direction_accuracy_pct"],
        }

    # 三只股票 1 步预测的平均指标
    avg_mape = round(float(np.mean([summary[s]["mape_pct_h1"] for s in summary])), 2)
    avg_dir = round(float(np.mean([summary[s]["direction_accuracy_pct_h1"] for s in summary])), 2)
    best_mape = min(summary[s]["mape_pct_h1"] for s in summary)

    result = {
        "project": "MCP 多智能体金融助理系统 - EMA 股价预测回测",
        "params": {"alpha": ALPHA, "min_train": MIN_TRAIN, "horizons": HORIZONS},
        "per_stock": per_stock,
        "summary": {
            "avg_mape_pct_h1": avg_mape,
            "best_mape_pct_h1": best_mape,
            "avg_direction_accuracy_pct_h1": avg_dir,
        },
    }

    out_path = Path(__file__).parent / "ema_backtest_results.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 60)
    print("EMA 股价预测回测结果 (alpha=0.8)")
    print("=" * 60)
    for s, r in per_stock.items():
        h1 = r["h1"]
        print(f"[{s}] 样本={h1['samples']}  MAE={h1['mae']}  "
              f"MAPE={h1['mape_pct']}%  方向准确率={h1['direction_accuracy_pct']}%")
    print("-" * 60)
    print(f"三只股票 1 步预测平均 MAPE = {avg_mape}%")
    print(f"三只股票 1 步预测平均方向准确率 = {avg_dir}%")
    print(f"最优 MAPE = {best_mape}%")
    print("=" * 60)
    print(f"结果已写入: {out_path}")


if __name__ == "__main__":
    main()
