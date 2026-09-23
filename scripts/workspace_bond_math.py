"""Deterministic teaching calculations for regular fixed-rate coupon-date bonds.

No accrued interest, irregular coupons, options, or par-curve bootstrapping.
Rates are annual decimals and periods are remaining coupon payments.
"""
import math


def price_bond(face, coupon_rate, annual_yield, periods, frequency=2):
    for name,value in [('face',face),('coupon_rate',coupon_rate),('annual_yield',annual_yield)]:
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError(name+' must be a finite number')
    if face<=0 or coupon_rate<0:
        raise ValueError('Face must be positive and coupon rate nonnegative')
    if type(frequency) is not int or frequency not in (1,2,4,12):
        raise ValueError('Choose 1, 2, 4, or 12 payments per year')
    if type(periods) is not int or not 1<=periods<=1200:
        raise ValueError('Provide 1 to 1200 remaining coupon periods')
    base=1+annual_yield/frequency
    if base<=0:
        raise ValueError('Yield must leave a positive per-period discount base')
    coupon=face*coupon_rate/frequency
    payments=[]
    try:
        for k in range(1,periods+1):
            principal=face if k==periods else 0
            discount=base**(-k)
            present=(coupon+principal)*discount
            payments.append({'period':k,'years':k/frequency,'coupon':coupon,'principal':principal,
                             'cash_flow':coupon+principal,'discount_factor':discount,'present_value':present})
        price=math.fsum(row['present_value'] for row in payments)
        if not math.isfinite(price) or price<=0:
            raise ValueError('Inputs exceed the finite calculation range')
        macaulay=math.fsum(row['years']*row['present_value'] for row in payments)/price
        modified=macaulay/base
        dv01=price*modified*.0001
        convexity=math.fsum(row["period"]*(row["period"]+1)*row["present_value"] for row in payments)/(price*frequency**2*base**2)
        if not all(math.isfinite(v) for v in (macaulay,modified,dv01,convexity)):
            raise ValueError('Inputs exceed the finite calculation range')
    except (OverflowError,ZeroDivisionError) as exc:
        raise ValueError('Inputs exceed the finite calculation range') from exc
    return {'price':price,'payments':payments,'macaulay_duration_years':macaulay,
            'modified_duration_years':modified,'dv01_approx':dv01,
            'convexity_years_squared':convexity,
            'convention':'Regular coupon-date valuation; annual nominal yield compounded at payment frequency',
            'rate_unit':'annual_decimal','price_unit':'same currency as face','calculation_version':'coupon-date-v1'}
