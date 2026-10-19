import unittest

from zoids_app.combat import (
    RuleError, WeaponState, repair_health, rest_weapons, restore_repaired_weapon,
    use_weapon, vent_weapon, repair_weapon, RepairConfirmationRequired,
)


class HeatRulesTests(unittest.TestCase):
    def test_each_rating_allows_capacity_then_one_final_shot(self):
        for rating in (1, 2, 3):
            with self.subTest(rating=rating):
                weapon = WeaponState(heat_rating=rating)
                for _ in range(rating):
                    result = use_weapon(weapon)
                    self.assertFalse(result.broke_after_use)
                    weapon = result.weapon
                self.assertEqual(weapon.heat, rating)
                result = use_weapon(weapon)
                self.assertTrue(result.broke_after_use)
                self.assertEqual(result.weapon.heat, rating + 1)
                with self.assertRaises(RuleError):
                    use_weapon(result.weapon)

    def test_vent_before_overheat_allows_another_safe_use(self):
        weapon = WeaponState(heat_rating=3, heat=3)
        result = use_weapon(vent_weapon(weapon))
        self.assertEqual(result.weapon.heat, 3)
        self.assertFalse(result.weapon.broken)

    def test_cooling_cannot_repair_broken_weapon(self):
        broken = use_weapon(WeaponState(heat_rating=1, heat=1)).weapon
        for cooled in (vent_weapon(broken), rest_weapons((broken,))[0]):
            self.assertTrue(cooled.broken)
            with self.assertRaises(RuleError):
                use_weapon(cooled)

    def test_unrated_weapons_do_not_overheat(self):
        weapon = WeaponState()
        for _ in range(100):
            weapon = use_weapon(weapon).weapon
        self.assertEqual(weapon, WeaponState())

    def test_repair_resets_heat_and_restores_full_safe_capacity(self):
        for rating in (1, 2, 3):
            with self.subTest(rating=rating):
                broken = use_weapon(WeaponState(rating, heat=rating)).weapon
                repaired = restore_repaired_weapon(broken)
                self.assertEqual(repaired, WeaponState(rating))
                for _ in range(rating):
                    repaired = use_weapon(repaired).weapon
                    self.assertFalse(repaired.broken)
                self.assertTrue(use_weapon(repaired).weapon.broken)

    def test_vent_at_zero_and_rest_all_slots(self):
        self.assertEqual(vent_weapon(WeaponState(1)).heat, 0)
        weapons = tuple(WeaponState(3, heat=2) for _ in range(8))
        self.assertTrue(all(w.heat == 0 for w in rest_weapons(weapons)))


class WeaponRepairTests(unittest.TestCase):
    def test_flat_price_for_each_heat_rating(self):
        for rating in (1, 2, 3):
            with self.subTest(rating=rating):
                result = repair_weapon(WeaponState(rating, rating + 1, True), 12_000, current_health=100, maximum_health=100)
                self.assertEqual(result.weapon, WeaponState(rating))
                self.assertEqual((result.gold, result.cost), (2_000, 10_000))

    def test_exact_funds_and_no_duplicate_charge(self):
        result = repair_weapon(WeaponState(1, 2, True), 10_000, current_health=100, maximum_health=100)
        self.assertEqual(result.gold, 0)
        again = repair_weapon(result.weapon, result.gold, current_health=100, maximum_health=100)
        self.assertEqual((again.gold, again.cost), (0, 0))

    def test_insufficient_funds_leave_weapon_broken_and_hot(self):
        weapon = WeaponState(3, 4, True)
        with self.assertRaises(RuleError):
            repair_weapon(weapon, 9_999, current_health=100, maximum_health=100)
        self.assertEqual(weapon, WeaponState(3, 4, True))

    def test_intact_weapon_is_not_charged_or_cooled(self):
        weapon = WeaponState(3, 2)
        result = repair_weapon(weapon, 20_000, current_health=100, maximum_health=100)
        self.assertEqual((result.weapon, result.gold, result.cost), (weapon, 20_000, 0))

    def test_invalid_gold_rejected(self):
        for gold in (-1, True, 10_000.5):
            with self.assertRaises(RuleError):
                repair_weapon(WeaponState(1, 2, True), gold, current_health=100, maximum_health=100)

    def test_confirmation_threshold_is_strict_and_not_rounded(self):
        weapon = WeaponState(3, 4, True)
        for current, maximum in ((75, 100), (76, 100), (100, 100)):
            result = repair_weapon(weapon, 20_000, current_health=current, maximum_health=maximum)
            self.assertFalse(result.weapon.broken)
        for current, maximum in ((74, 100), (0, 100), (75, 101)):
            with self.assertRaises(RepairConfirmationRequired):
                repair_weapon(weapon, 20_000, current_health=current, maximum_health=maximum)
        self.assertEqual(weapon, WeaponState(3, 4, True))

    def test_warning_quotes_costs_and_health_shortfall(self):
        with self.assertRaises(RepairConfirmationRequired) as caught:
            repair_weapon(WeaponState(1, 2, True), 10_100, current_health=50, maximum_health=100)
        warning = caught.exception
        self.assertEqual((warning.weapon_repair_cost, warning.gold_after_repair, warning.health_repair_cost), (10_000, 100, 500))
        self.assertIn("not have enough gold", str(warning))

    def test_warning_even_when_health_repair_is_affordable(self):
        with self.assertRaises(RepairConfirmationRequired) as caught:
            repair_weapon(WeaponState(1, 2, True), 20_000, current_health=50, maximum_health=100)
        self.assertNotIn("not have enough gold", str(caught.exception))

    def test_confirmed_repair_charges_once_and_preserves_rules(self):
        result = repair_weapon(WeaponState(1, 2, True), 10_000, current_health=50, maximum_health=100, confirmed=True)
        self.assertEqual((result.weapon, result.gold, result.cost), (WeaponState(1), 0, 10_000))
        with self.assertRaises(RuleError) as caught:
            repair_weapon(WeaponState(1, 2, True), 9_999, current_health=50, maximum_health=100, confirmed=True)
        self.assertNotIsInstance(caught.exception, RepairConfirmationRequired)

    def test_intact_weapon_needs_no_confirmation(self):
        result = repair_weapon(WeaponState(1), 10_000, current_health=50, maximum_health=100)
        self.assertEqual(result.cost, 0)

    def test_invalid_health_and_confirmation_rejected(self):
        for current, maximum in ((-1, 100), (0, 0), (1, -1), (True, 100)):
            with self.assertRaises(RuleError):
                repair_weapon(WeaponState(1, 2, True), 10_000, current_health=current, maximum_health=maximum)
        with self.assertRaises(RuleError):
            repair_weapon(WeaponState(1, 2, True), 10_000, current_health=50, maximum_health=100, confirmed="yes")


class HealthRepairTests(unittest.TestCase):
    def test_full_repair_charges_only_missing_health(self):
        result = repair_health(100, 144, 500)
        self.assertEqual((result.health, result.gold, result.cost), (144, 60, 440))

    def test_insufficient_gold_rejects_full_repair(self):
        with self.assertRaises(RuleError):
            repair_health(100, 144, 439)

    def test_partial_repair_and_exact_funds(self):
        result = repair_health(100, 144, 50, points=5)
        self.assertEqual((result.health, result.gold, result.restored), (105, 0, 5))

    def test_request_cannot_overheal_or_overcharge(self):
        result = repair_health(140, 144, 100, points=20)
        self.assertEqual((result.health, result.cost, result.gold), (144, 40, 60))

    def test_no_charge_at_or_above_maximum(self):
        for health in (144, 150):
            result = repair_health(health, 144, 0)
            self.assertEqual((result.health, result.cost), (health, 0))

    def test_invalid_values_rejected(self):
        for args in ((-1, 144, 100), (100, 144, -1), (100, 144, True)):
            with self.assertRaises(RuleError):
                repair_health(*args)


if __name__ == "__main__":
    unittest.main()
