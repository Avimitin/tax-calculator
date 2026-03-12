#!/usr/bin/env python3
"""
税务统筹计算与可视化脚本
通过穷举个人年度税前工资，找出在给定年度总盘子下税负最低的最优分配方案
"""

import argparse
import plotly.graph_objects as go
from typing import List, Tuple

RATE_INSURANCE = 0.20
CAP_BASE = 400000
BASIC_DEDUCTION = 60000
CIT_RATE = 0.05
DIVIDEND_TAX_RATE = 0.20

IIT_BRACKETS = [
    (36000, 0.03, 0),
    (144000, 0.10, 2520),
    (300000, 0.20, 16920),
    (420000, 0.25, 31920),
    (660000, 0.30, 52920),
    (960000, 0.35, 85920),
    (float("inf"), 0.45, 181920),
]


def calc_insurance(salary: float) -> float:
    return min(salary, CAP_BASE) * RATE_INSURANCE


def calc_iit(taxable_income: float) -> float:
    if taxable_income <= 0:
        return 0.0

    for threshold, rate, quick_deduction in IIT_BRACKETS:
        if taxable_income <= threshold:
            return taxable_income * rate - quick_deduction

    return taxable_income * 0.45 - 181920


def calc_taxes(salary: float, total_pool: float, deduct: float) -> dict:
    ins = calc_insurance(salary)

    taxable_income = max(0, salary - BASIC_DEDUCTION - ins - deduct)
    iit = calc_iit(taxable_income)

    profit = total_pool - salary
    cit = profit * CIT_RATE

    profit_after = profit - cit
    div_tax = profit_after * DIVIDEND_TAX_RATE

    total_tax = iit + cit + div_tax

    return {
        "salary": salary,
        "insurance": ins,
        "taxable_income": taxable_income,
        "iit": iit,
        "profit": profit,
        "cit": cit,
        "div_tax": div_tax,
        "total_tax": total_tax,
        "net_received": total_pool - total_tax,
    }


def iterate_scenarios(total_pool: float, deduct: float, step: float) -> List[dict]:
    results = []
    salary = 0

    while salary <= total_pool:
        result = calc_taxes(salary, total_pool, deduct)
        results.append(result)
        salary += step

    return results


def find_optimal(results: List[dict]) -> dict:
    return min(results, key=lambda x: x["total_tax"])


def create_visualization(
    results: List[dict], optimal: dict, total_pool: float
) -> go.Figure:
    salaries = [r["salary"] for r in results]
    total_taxes = [r["total_tax"] for r in results]

    customdata = []
    for r in results:
        customdata.append(
            [
                r["salary"],
                total_pool - r["salary"],
                r["total_tax"],
                r["iit"],
                r["cit"],
                r["div_tax"],
                r["net_received"],
                r["insurance"],
            ]
        )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=salaries,
            y=total_taxes,
            mode="lines",
            name="总税负曲线",
            line=dict(color="#1f77b4", width=2),
            customdata=customdata,
            hovertemplate=(
                "<b>分配方案:</b> 工资 %{customdata[0]:,.0f} 元 / 分红利润 %{customdata[1]:,.0f} 元<br>"
                "<b>总缴税:</b> %{customdata[2]:,.0f} 元<br>"
                "<b>包含</b> -> 工资个税: %{customdata[3]:,.0f} 元 | 企业所得税: %{customdata[4]:,.0f} 元 | 分红个税: %{customdata[5]:,.0f} 元<br>"
                "<b>实际净到手总额 (含免税公积金):</b> %{customdata[6]:,.0f} 元<br>"
                "<b>五险一金个人部分:</b> %{customdata[7]:,.0f} 元<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[optimal["salary"]],
            y=[optimal["total_tax"]],
            mode="markers+text",
            name="最优方案",
            marker=dict(color="red", size=15, symbol="star"),
            text=["最优"],
            textposition="top center",
            textfont=dict(color="red", size=14, family="Arial Black"),
            customdata=[
                [
                    optimal["salary"],
                    total_pool - optimal["salary"],
                    optimal["total_tax"],
                    optimal["iit"],
                    optimal["cit"],
                    optimal["div_tax"],
                    optimal["net_received"],
                    optimal["insurance"],
                ]
            ],
            hovertemplate=(
                "<b>*** 最优分配方案 ***</b><br>"
                "<b>分配方案:</b> 工资 %{customdata[0]:,.0f} 元 / 分红利润 %{customdata[1]:,.0f} 元<br>"
                "<b>总缴税:</b> %{customdata[2]:,.0f} 元<br>"
                "<b>包含</b> -> 工资个税: %{customdata[3]:,.0f} 元 | 企业所得税: %{customdata[4]:,.0f} 元 | 分红个税: %{customdata[5]:,.0f} 元<br>"
                "<b>实际净到手总额 (含免税公积金):</b> %{customdata[6]:,.0f} 元<br>"
                "<b>五险一金个人部分:</b> %{customdata[7]:,.0f} 元<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text=f"税务统筹分析 - 年度总盘子: {total_pool:,.0f} 元",
            font=dict(size=18),
        ),
        xaxis=dict(
            title="个人年度税前工资 (Salary)",
            tickformat=",.0f",
            gridcolor="lightgray",
        ),
        yaxis=dict(
            title="实际总缴税金额 (Total Tax)",
            tickformat=",.0f",
            gridcolor="lightgray",
        ),
        hovermode="closest",
        template="plotly_white",
        width=1200,
        height=700,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    return fig


def print_optimal_summary(optimal: dict, total_pool: float, deduct: float):
    print("\n" + "=" * 60)
    print("                    最优税务统筹方案")
    print("=" * 60)
    print(f"\n【输入参数】")
    print(f"  年度总盘子 (M):     {total_pool:>15,.0f} 元")
    print(f"  专项附加扣除:       {deduct:>15,.0f} 元")
    print(f"\n【最优分配方案】")
    print(f"  个人税前工资:       {optimal['salary']:>15,.0f} 元")
    print(f"  公司留存利润:       {optimal['profit']:>15,.0f} 元")
    print(f"\n【税费明细】")
    print(f"  五险一金(个人):     {optimal['insurance']:>15,.0f} 元")
    print(f"  应纳税所得额:       {optimal['taxable_income']:>15,.0f} 元")
    print(f"  个人所得税(IIT):    {optimal['iit']:>15,.0f} 元")
    print(f"  企业所得税(CIT):    {optimal['cit']:>15,.0f} 元")
    print(f"  分红个税(DivTax):   {optimal['div_tax']:>15,.0f} 元")
    print(f"  ----------------------------------------")
    print(f"  总税负(Total Tax):  {optimal['total_tax']:>15,.0f} 元")
    print(f"\n【最终结果】")
    print(f"  实际净到手总额:     {optimal['net_received']:>15,.0f} 元")
    print(f"  有效税率:           {(optimal['total_tax'] / total_pool * 100):>14.2f} %")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="税务统筹计算与可视化工具 - 找出最优工资与分红分配方案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tax_optimizer.py
  python tax_optimizer.py -p 1500000 -d 24000 -s 5000
  python tax_optimizer.py --pool 2000000 --deduct 36000 --step 2000
        """,
    )

    parser.add_argument(
        "-p",
        "--pool",
        type=float,
        default=1000000,
        help="企业分配给个人的年度总盘子 (默认: 1000000)",
    )
    parser.add_argument(
        "-d",
        "--deduct",
        type=float,
        default=18000,
        help="个人年度专项附加扣除总额 (默认: 18000)",
    )
    parser.add_argument(
        "-s", "--step", type=float, default=10000, help="穷举工资时的步长 (默认: 10000)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="tax_optimization.html",
        help="输出HTML文件名 (默认: tax_optimization.html)",
    )

    args = parser.parse_args()

    print(
        f"\n正在计算: 年度总盘子={args.pool:,.0f}, 专项扣除={args.deduct:,.0f}, 步长={args.step:,.0f}"
    )

    results = iterate_scenarios(args.pool, args.deduct, args.step)
    optimal = find_optimal(results)

    print_optimal_summary(optimal, args.pool, args.deduct)

    fig = create_visualization(results, optimal, args.pool)
    fig.write_html(args.output)
    print(f"可视化图表已保存至: {args.output}")
    print(f"请在浏览器中打开查看交互式图表\n")


if __name__ == "__main__":
    main()
