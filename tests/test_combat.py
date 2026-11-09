import unittest

from zoids_app.combat import (
    RuleError, WeaponState, repair_health, restore_repaired_weapon,
    use_weapon, repair_weapon, RepairConfirmationRequired,
)


class EnergyRulesTests(unittest.TestCase):
    def test_exact_energy_and_zero_cost(self):
        result = use_weapon(WeaponState(), current_energy=12, energy_cost=12)
        self.assertEqual(result.energy, 0)
        self.assertFalse(result.weapon.broken)
        self.assertEqual(use_weapon(result.weapon, current_energy=0, energy_cost=0).energy, 0)

    def test_unaffordable_or_broken_weapon_cannot_fire(self):
        for state, energy in ((WeaponState(), 11), (WeaponState(True), 20)):
            with self.assertRaises(RuleError):
                use_weapon(state, current_energy=energy, energy_cost=12)

    def test_invalid_energy_rejected(self):
        for invalid in (-1, True, 1.5, None):
            with self.assertRaises(RuleError):
                use_weapon(WeaponState(), current_energy=invalid, energy_cost=0)
            with self.assertRaises(RuleError):
                use_weapon(WeaponState(), current_energy=10, energy_cost=invalid)


class WeaponRepairTests(unittest.TestCase):
    def test_flat_price(self):
        result = repair_weapon(WeaponState(True), 12_000, current_health=100, maximum_health=100)
        self.assertEqual(result.weapon, WeaponState())
        self.assertEqual((result.gold, result.cost), (2_000, 10_000))

    def test_exact_funds_and_no_duplicate_charge(self):
        result = repair_weapon(WeaponState(True), 10_000, current_health=100, maximum_health=100)
        self.assertEqual(result.gold, 0)
        again = repair_weapon(result.weapon, result.gold, current_health=100, maximum_health=100)
        self.assertEqual((again.gold, again.cost), (0, 0))

    def test_insufficient_funds_leave_weapon_broken(self):
        weapon = WeaponState(True)
        with self.assertRaises(RuleError):
            repair_weapon(weapon, 9_999, current_health=100, maximum_health=100)
        self.assertEqual(weapon, WeaponState(True))

    def test_intact_weapon_is_not_charged(self):
        weapon = WeaponState()
        result = repair_weapon(weapon, 20_000, current_health=100, maximum_health=100)
        self.assertEqual((result.weapon, result.gold, result.cost), (weapon, 20_000, 0))

    def test_invalid_gold_rejected(self):
        for gold in (-1, True, 10_000.5):
            with self.assertRaises(RuleError):
                repair_weapon(WeaponState(True), gold, current_health=100, maximum_health=100)

    def test_confirmation_threshold_is_strict_and_not_rounded(self):
        weapon = WeaponState(True)
        for current, maximum in ((75, 100), (76, 100), (100, 100)):
            result = repair_weapon(weapon, 20_000, current_health=current, maximum_health=maximum)
            self.assertFalse(result.weapon.broken)
        for current, maximum in ((74, 100), (0, 100), (75, 101)):
            with self.assertRaises(RepairConfirmationRequired):
                repair_weapon(weapon, 20_000, current_health=current, maximum_health=maximum)
        self.assertEqual(weapon, WeaponState(True))

    def test_warning_quotes_costs_and_health_shortfall(self):
        with self.assertRaises(RepairConfirmationRequired) as caught:
            repair_weapon(WeaponState(True), 10_100, current_health=50, maximum_health=100)
        warning = caught.exception
        self.assertEqual((warning.weapon_repair_cost, warning.gold_after_repair, warning.health_repair_cost), (10_000, 100, 500))
        self.assertIn("not have enough gold", str(warning))

    def test_warning_even_when_health_repair_is_affordable(self):
        with self.assertRaises(RepairConfirmationRequired) as caught:
            repair_weapon(WeaponState(True), 20_000, current_health=50, maximum_health=100)
        self.assertNotIn("not have enough gold", str(caught.exception))

    def test_confirmed_repair_charges_once_and_preserves_rules(self):
        result = repair_weapon(WeaponState(True), 10_000, current_health=50, maximum_health=100, confirmed=True)
        self.assertEqual((result.weapon, result.gold, result.cost), (WeaponState(), 0, 10_000))
        with self.assertRaises(RuleError) as caught:
            repair_weapon(WeaponState(True), 9_999, current_health=50, maximum_health=100, confirmed=True)
        self.assertNotIsInstance(caught.exception, RepairConfirmationRequired)

    def test_intact_weapon_needs_no_confirmation(self):
        result = repair_weapon(WeaponState(), 10_000, current_health=50, maximum_health=100)
        self.assertEqual(result.cost, 0)

    def test_invalid_health_and_confirmation_rejected(self):
        for current, maximum in ((-1, 100), (0, 0), (1, -1), (True, 100)):
            with self.assertRaises(RuleError):
                repair_weapon(WeaponState(True), 10_000, current_health=current, maximum_health=maximum)
        with self.assertRaises(RuleError):
            repair_weapon(WeaponState(True), 10_000, current_health=50, maximum_health=100, confirmed="yes")


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
