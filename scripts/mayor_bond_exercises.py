"""Reproducible teaching scenarios, not historical NYC bond transactions."""
import math
from workspace_bond_math import price_bond

SOURCE = 'https://www.nyc.gov/site/dcas/about/green-book-mayors-of-the-city-of-new-york.page'
ERAS = {
 'giuliani': ('Rudolph Giuliani', '1994–2001', '1994-01-03', .06, .065, 'price'),
 'bloomberg': ('Michael Bloomberg', '2002–2013', '2008-09-15', .05, .04, 'price'),
 'de_blasio': ('Bill de Blasio', '2014–2021', '2020-03-16', .04, .02, 'modified_duration_years'),
 'adams': ('Eric Adams', '2022–2025', '2022-06-15', .04, .05, 'dv01_approx'),
 'mamdani': ('Zohran Mamdani', '2026–present (verified 2026-09-23)', '2026-09-22', .05, .055, 'convexity_years_squared'),
}


def exercise(era):
    if era not in ERAS:
        raise ValueError('Choose giuliani, bloomberg, de_blasio, adams, or mamdani')
    name, period, date, coupon, yield_, metric = ERAS[era]
    return {'exercise_id': era+'-v1', 'mayor': name, 'administration': period,
            'administration_source': SOURCE, 'context_date': date,
            'inputs': {'face': 1000, 'coupon_rate': coupon, 'annual_yield': yield_, 'periods': 20, 'frequency': 2},
            'question': 'Calculate '+metric+' and show your formula and units.', 'metric': metric,
            'tolerance_absolute': .01 if metric == 'price' else .001,
            'assumptions': ['Synthetic regular coupon-date bond, USD face value',
                'No accrued interest, default, tax effects, calls, or irregular coupons',
                'Coupon and yield are teaching assumptions, NOT historical NYC borrowing rates',
                'Treasury context date is selected, not representative of the whole administration',
                'No claim that a mayor caused Treasury yield changes'],
            'workflow': 'Show inputs and ask for confirmation. Fetch dated Treasury context separately. Ask the exercise without revealing the answer. Grade only after the user submits a numeric answer with units and working.'}


def grade(era, answer, unit):
    task = exercise(era)
    if type(answer) not in (int, float) or not math.isfinite(answer):
        raise ValueError('Answer must be a finite number')
    expected_unit = {'price': 'USD', 'modified_duration_years': 'years', 'dv01_approx': 'USD/bp',
                     'convexity_years_squared': 'years^2'}[task['metric']]
    if unit != expected_unit:
        return {'status': 'needs_unit_correction', 'expected_unit': expected_unit, 'submitted_unit': unit,
                'exercise_id': task['exercise_id'], 'numeric_grade': None}
    correct = price_bond(**task['inputs'])[task['metric']]
    return {'exercise_id': task['exercise_id'], 'submitted_answer': answer, 'unit': unit,
            'expected_answer': correct, 'absolute_error': abs(answer-correct),
            'tolerance_absolute': task['tolerance_absolute'],
            'passed': abs(answer-correct) <= task['tolerance_absolute'],
            'grading_scope': 'Deterministic numeric answer only. Reasoning and transcription still require review.',
            'inputs': task['inputs']}
