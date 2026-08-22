from datetime import date

from roxy_os.home_weekly_plans import create_local_weekly_plan, update_weekly_plan_day, weekly_plan_shopping_items


def test_weekly_styles_generate_complete_real_meals_without_openai():
    snapshot = {"profile": {"allergies": [], "dislikes": []}}
    for style in ("fitness", "normal", "quick", "weight_loss"):
        plan = create_local_weekly_plan(
            snapshot,
            style=style,
            people=2,
            max_minutes=20 if style == "quick" else 40,
            weekly_budget=85,
        )
        assert plan["style"] == style
        assert len(plan["days"]) == 7
        assert all(len(day["meals"]) == 3 for day in plan["days"])
        assert all(meal["ingredients"] or meal["key"] == "leftovers" for day in plan["days"] for meal in day["meals"])
        assert date.fromisoformat(plan["days"][0]["date"]).weekday() == 0


def test_weekly_plan_scales_household_and_can_exclude_ready_days():
    one = create_local_weekly_plan({}, style="normal", people=1, max_minutes=40, weekly_budget=80)
    two = create_local_weekly_plan({}, style="normal", people=2, max_minutes=40, weekly_budget=80)
    one_items = weekly_plan_shopping_items(one)
    two_items = weekly_plan_shopping_items(two)
    one_arroz = next(row for row in one_items if row["name"] == "Arroz")
    two_arroz = next(row for row in two_items if row["name"] == "Arroz")
    without_monday = weekly_plan_shopping_items(two, {0})

    assert two_arroz["quantity"] == one_arroz["quantity"] * 2
    assert sum(row["quantity"] for row in without_monday) < sum(row["quantity"] for row in two_items)


def test_weekly_plan_avoids_registered_allergy_when_possible():
    plan = create_local_weekly_plan(
        {"profile": {"allergies": ["huevo"], "dislikes": []}},
        style="normal",
        people=2,
        max_minutes=30,
        weekly_budget=85,
    )
    ingredients = " ".join(
        row["name"].lower()
        for day in plan["days"]
        for meal in day["meals"]
        for row in meal["ingredients"]
    )
    assert "huevo" not in ingredients


def test_weekly_plan_can_focus_on_two_meals_and_build_batch_sessions():
    plan = create_local_weekly_plan(
        {},
        style="quick",
        people=2,
        max_minutes=20,
        weekly_budget=85,
        cook_days=2,
        meal_scope="lunch_dinner",
    )

    assert all([meal["meal_type"] for meal in day["meals"]] == ["lunch", "dinner"] for day in plan["days"])
    assert len(plan["prep_sessions"]) == 2
    assert all(session["tasks"] for session in plan["prep_sessions"])
    assert plan["days"][1]["reuse_note"]


def test_live_week_reschedules_skipped_day_and_excludes_covered_days_from_shopping():
    plan = create_local_weekly_plan({}, style="normal", people=2, max_minutes=40, weekly_budget=85)
    monday_titles = [meal["title"] for meal in plan["days"][0]["meals"]]
    tuesday_titles = [meal["title"] for meal in plan["days"][1]["meals"]]
    full_items = weekly_plan_shopping_items(plan)

    update_weekly_plan_day(plan, day_index=0, action="skip")
    assert plan["days"][0]["status"] == "skipped"
    assert [meal["title"] for meal in plan["days"][1]["meals"]] == monday_titles
    assert [meal["title"] for meal in plan["days"][0]["meals"]] == tuesday_titles
    assert len(weekly_plan_shopping_items(plan)) <= len(full_items)

    update_weekly_plan_day(plan, day_index=0, action="reset")
    assert plan["days"][0]["status"] == "scheduled"
    assert [meal["title"] for meal in plan["days"][0]["meals"]] == monday_titles

    update_weekly_plan_day(plan, day_index=1, action="leftovers")
    assert plan["days"][1]["status"] == "leftovers"
    assert sum(row["quantity"] for row in weekly_plan_shopping_items(plan)) < sum(row["quantity"] for row in full_items)
