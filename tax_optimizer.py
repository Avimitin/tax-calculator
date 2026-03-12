#!/usr/bin/env python3
"""
税务统筹计算与可视化脚本 (年终奖单独计税版)
通过穷举个人年度税前工资和年终奖，找出在给定年度总盘子下税负最低的最优分配方案
"""

import argparse
import plotly.graph_objects as go
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import numpy as np

@dataclass
class CityProfile:
    name: str
    monthly_cap: float
    monthly_floor: float
    ee_pension: float = 0.08
    ee_medical: float = 0.02
    ee_unemployment: float = 0.005
    ee_hpf: float = 0.12
    er_pension: float = 0.16
    er_medical: float = 0.09
    er_unemployment: float = 0.005
    er_maternity: float = 0.008
    er_injury: float = 0.002
    er_hpf: float = 0.12

    @property
    def ee_total_rate(self) -> float:
        return self.ee_pension + self.ee_medical + self.ee_unemployment + self.ee_hpf

    @property
    def er_total_rate(self) -> float:
        return (
            self.er_pension
            + self.er_medical
            + self.er_unemployment
            + self.er_maternity
            + self.er_injury
            + self.er_hpf
        )

PROFILES = {
    "beijing": CityProfile(
        name="北京",
        monthly_cap=35283,
        monthly_floor=6821,
        ee_hpf=0.12,
        er_hpf=0.12,
        er_medical=0.098,
    ),
    "shanghai": CityProfile(
        name="上海",
        monthly_cap=36921,
        monthly_floor=7310,
        ee_hpf=0.07,  # Standard is 7%, can be up to 12%
        er_hpf=0.07,
        er_medical=0.10,
    ),
    "wuhan": CityProfile(
        name="武汉",
        monthly_cap=34863,
        monthly_floor=7489,
        ee_hpf=0.12,
        er_hpf=0.12,
        er_medical=0.087,
    ),
}

BASIC_DEDUCTION = 60000
DEFAULT_CIT_RATE = 0.05
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

BONUS_BRACKETS = [
    (3000, 0.03, 0),
    (12000, 0.10, 210),
    (25000, 0.20, 1410),
    (35000, 0.25, 2660),
    (55000, 0.30, 4410),
    (80000, 0.35, 7160),
    (float("inf"), 0.45, 15160),
]


def calc_insurance_base(salary: float, profile: CityProfile) -> float:
    # Monthly salary for insurance calculation
    monthly = salary / 12
    base = max(min(monthly, profile.monthly_cap), profile.monthly_floor)
    return base * 12


def calc_personal_insurance(salary: float, profile: CityProfile) -> float:
    base = calc_insurance_base(salary, profile)
    return base * (profile.ee_total_rate - profile.ee_hpf) + base * profile.ee_hpf


def calc_company_insurance(salary: float, profile: CityProfile) -> float:
    base = calc_insurance_base(salary, profile)
    return base * profile.er_total_rate


def calc_iit(taxable_income: float) -> float:
    if taxable_income <= 0:
        return 0.0

    for threshold, rate, quick_deduction in IIT_BRACKETS:
        if taxable_income <= threshold:
            return taxable_income * rate - quick_deduction

    return taxable_income * 0.45 - 181920


def calc_bonus_tax(bonus: float, unused_deduction: float = 0) -> float:
    if bonus <= 0:
        return 0.0

    # If salary is low, deduct the unused portion from the bonus first
    taxable_bonus = max(0, bonus - unused_deduction)
    if taxable_bonus == 0:
        return 0.0

    q = taxable_bonus / 12

    for threshold, rate, quick_deduction in BONUS_BRACKETS:
        if q <= threshold:
            return taxable_bonus * rate - quick_deduction

    return taxable_bonus * 0.45 - 15160


def calc_taxes(
    salary: float,
    bonus: float,
    total_pool: float,
    deduct: float,
    cit_rate: float,
    profile: CityProfile,
) -> Optional[dict]:
    personal_ins = calc_personal_insurance(salary, profile)
    company_ins = calc_company_insurance(salary, profile)

    total_cost = salary + bonus + company_ins
    if total_cost > total_pool + 0.01:  # Allow small float epsilon
        return None

    # IIT on Salary
    # Monthly standard deduction is 5000, annual 60000
    pre_tax_income = salary - personal_ins
    taxable_income = max(0, pre_tax_income - BASIC_DEDUCTION - deduct)
    iit = calc_iit(taxable_income)

    # Bonus Tax with unused deduction logic
    # unused_deduction = max(0, 60000 + deduct + personal_ins - salary)
    # Actually, official rule: if (salary - insurance) < 5000, then bonus = bonus - (5000 - (salary - insurance))
    # Annually: if (salary - insurance) < 60000, then bonus = bonus - (60000 - (salary - insurance))
    # We also consider 'deduct' (Special Add-on Deductions) if they are not fully used by salary?
    # Usually, special deductions apply to comprehensive income.
    # For SEPARATE bonus tax, only the basic 5000/mo threshold overflow applies.
    unused_basic_deduction = max(0, BASIC_DEDUCTION - pre_tax_income)
    bonus_tax = calc_bonus_tax(bonus, unused_basic_deduction)

    profit = total_pool - salary - bonus - company_ins
    cit = profit * cit_rate

    profit_after = profit - cit
    div_tax = profit_after * DIVIDEND_TAX_RATE

    total_tax = iit + bonus_tax + cit + div_tax

    # Calculations for wealth breakdown
    base = calc_insurance_base(salary, profile)
    hpf_personal = base * profile.ee_hpf
    hpf_company = base * profile.er_hpf
    total_hpf = hpf_personal + hpf_company

    liquid_cash = (
        salary - personal_ins - iit + bonus - bonus_tax + profit_after - div_tax
    )
    real_liquid_wealth = liquid_cash + total_hpf

    sunk_social_cost = personal_ins - hpf_personal + company_ins - hpf_company

    return {
        "salary": salary,
        "bonus": bonus,
        "personal_insurance": personal_ins,
        "company_insurance": company_ins,
        "taxable_income": taxable_income,
        "iit": iit,
        "bonus_tax": bonus_tax,
        "profit": profit,
        "cit": cit,
        "div_tax": div_tax,
        "total_tax": total_tax,
        "net_received": total_pool - total_tax,
        "total_cost": total_cost,
        "total_hpf": total_hpf,
        "liquid_cash": liquid_cash,
        "real_liquid_wealth": real_liquid_wealth,
        "sunk_social_cost": sunk_social_cost,
    }


def iterate_scenarios(
    total_pool: float, deduct: float, step: float, cit_rate: float, profile: CityProfile
) -> List[dict]:
    results = []
    # Optimization: Start salary at 0, but step wisely
    salary = 0

    while salary <= total_pool:
        # Check if company insurance alone exceeds pool
        company_ins_at_zero_bonus = calc_company_insurance(salary, profile)
        if salary + company_ins_at_zero_bonus > total_pool + 0.01:
            break

        bonus = 0
        while True:
            result = calc_taxes(salary, bonus, total_pool, deduct, cit_rate, profile)
            if result is None:
                break
            results.append(result)
            bonus += step

            if bonus > total_pool:
                break

        salary += step

    return results


def find_optimal(results: List[dict]) -> dict:
    # Wealth maximization is usually the goal, not just tax minimization
    return max(results, key=lambda x: x["real_liquid_wealth"])


def create_heatmap(
    results: List[dict],
    optimal: dict,
    total_pool: float,
    profile: CityProfile,
) -> go.Figure:
    salaries = sorted(list(set(r["salary"] for r in results)))
    bonuses = sorted(list(set(r["bonus"] for r in results)))

    # Use Real Liquid Wealth for the color scale
    z_matrix = np.full((len(bonuses), len(salaries)), np.nan)
    # Custom data for hover: [liquid_cash, total_hpf, iit, bonus_tax, cit, div_tax, sunk_cost]
    custom_matrix = np.full((len(bonuses), len(salaries), 7), np.nan)

    result_map = {}
    for r in results:
        key = (r["salary"], r["bonus"])
        result_map[key] = r

    for i, bonus in enumerate(bonuses):
        for j, salary in enumerate(salaries):
            key = (salary, bonus)
            if key in result_map:
                r = result_map[key]
                z_matrix[i, j] = r["real_liquid_wealth"]
                custom_matrix[i, j] = [
                    r["liquid_cash"],
                    r["total_hpf"],
                    r["iit"],
                    r["bonus_tax"],
                    r["cit"],
                    r["div_tax"],
                    r["sunk_social_cost"],
                ]

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            z=z_matrix,
            x=salaries,
            y=bonuses,
            customdata=custom_matrix,
            colorscale="Viridis",
            colorbar=dict(
                title=dict(text="真实财富 (元)", side="right"),
                tickformat=",.0f",
            ),
            hovertemplate=(
                "<b>分配方案</b><br>"
                "工资: %{x:,.0f} 元<br>"
                "年终奖: %{y:,.0f} 元<br><br>"
                "<b>财富组成</b><br>"
                "真实财富: %{z:,.0f} 元<br>"
                "  -> 纯现金: %{customdata[0]:,.0f} 元<br>"
                "  -> 公积金: %{customdata[1]:,.0f} 元<br><br>"
                "<b>税费支出</b><br>"
                "工资个税: %{customdata[2]:,.0f} 元<br>"
                "年终奖税: %{customdata[3]:,.0f} 元<br>"
                "企业所得税: %{customdata[4]:,.0f} 元<br>"
                "分红个税: %{customdata[5]:,.0f} 元<br>"
                "社保沉没: %{customdata[6]:,.0f} 元<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[optimal["salary"]],
            y=[optimal["bonus"]],
            mode="markers+text",
            name="最优方案",
            marker=dict(color="red", size=15, symbol="star"),
            text=["★ 最优"],
            textposition="top center",
            hovertemplate=(
                "<b>*** 最优分配方案 ***</b><br><br>"
                "工资: %{x:,.0f} 元<br>"
                "年终奖: %{y:,.0f} 元<br><br>"
                f"真实财富: {optimal['real_liquid_wealth']:,.0f} 元<br>"
                f"  -> 纯现金: {optimal['liquid_cash']:,.0f} 元<br>"
                f"  -> 公积金: {optimal['total_hpf']:,.0f} 元<br><br>"
                f"总税费: {optimal['total_tax']:,.0f} 元<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"税务统筹热力图 ({profile.name}) - 年度总盘子: {total_pool:,.0f}",
        xaxis_title="年度税前工资",
        yaxis_title="年终奖",
        template="plotly_white",
    )

    return fig


def print_optimal_summary(
    optimal: dict, total_pool: float, deduct: float, cit_rate: float, profile: CityProfile
):
    print("\n" + "=" * 70)
    print(f"               最优税务统筹方案 - {profile.name} (2025版)")
    print("=" * 70)
    print(f"\n【城市配置: {profile.name}】")
    print(f"  社保公积金上限:          {profile.monthly_cap * 12:>15,.0f} 元/年")
    print(f"  社保公积金下限:          {profile.monthly_floor * 12:>15,.0f} 元/年")
    print(f"\n【输入参数】")
    print(f"  年度总盘子 (M):          {total_pool:>15,.0f} 元")
    print(f"  专项附加扣除:            {deduct:>15,.0f} 元")
    print(f"  企业所得税率:            {cit_rate:>14.0%}")
    print(f"\n【分配参数】")
    print(f"  工资:                    {optimal['salary']:>15,.0f} 元")
    print(f"  年终奖:                  {optimal['bonus']:>15,.0f} 元")
    print(f"  公司统筹总成本:          {optimal['company_insurance']:>15,.0f} 元")
    print(f"  剩余分红利润:            {optimal['profit']:>15,.0f} 元")
    print(f"\n【政府税费总损耗】总计:   {optimal['total_tax']:>15,.0f} 元")
    print(f"  工资个税(IIT):           {optimal['iit']:>15,.0f} 元")
    print(f"  年终奖个税(BonusTax):    {optimal['bonus_tax']:>15,.0f} 元")
    print(f"  企业所得税(CIT):         {optimal['cit']:>15,.0f} 元")
    print(f"  分红个税(DivTax):        {optimal['div_tax']:>15,.0f} 元")
    print(f"\n【个人真实财富】总计:     {optimal['real_liquid_wealth']:>15,.0f} 元")
    print(f"  -> 纯现金(可自由支配):   {optimal['liquid_cash']:>15,.0f} 元")
    print(f"  -> 公积金(可提取抵扣):   {optimal['total_hpf']:>15,.0f} 元")
    print(f"\n【其他指标】")
    print(f"  有效税率 (含社保沉没):   {((total_pool - optimal['real_liquid_wealth']) / total_pool * 100):>14.2f} %")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="税务统筹计算与可视化工具 (2025 Profile版)")
    parser.add_argument("-p", "--pool", type=float, default=1000000)
    parser.add_argument("-d", "--deduct", type=float, default=18000)
    parser.add_argument("-s", "--step", type=float, default=10000)
    parser.add_argument("-c", "--city", choices=PROFILES.keys(), default="beijing")
    parser.add_argument("--cit", type=float, default=DEFAULT_CIT_RATE)
    parser.add_argument("-o", "--output", type=str, default="tax_optimization_bonus.html")

    args = parser.parse_args()
    profile = PROFILES[args.city]

    results = iterate_scenarios(args.pool, args.deduct, args.step, args.cit, profile)
    if not results:
        print("错误: 在当前总盘子下无法找到可行方案。请增加总盘子或减少步长。")
        return

    optimal = find_optimal(results)
    print_optimal_summary(optimal, args.pool, args.deduct, args.cit, profile)

    fig = create_heatmap(results, optimal, args.pool, profile)
    fig.write_html(args.output)
    print(f"热力图已保存至: {args.output}")


if __name__ == "__main__":
    main()
