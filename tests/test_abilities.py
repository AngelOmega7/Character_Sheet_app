import unittest

from zoids_app.abilities import AbilityLoadout, activate_ability, deactivate_ability, learn_ability, validate_loadout
from zoids_app.catalog import Catalog
from zoids_app.combat import RuleError


class AbilityOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def test_acquiring_an_active_upgrade_replaces_rank_in_same_slot(self):
        original = AbilityLoadout((None, "Small Expert"), ("Medium Expert",))
        upgraded = learn_ability(original, "Small Expert 2", self.catalog)
        self.assertEqual(upgraded.active, (None, "abilities:small_expert_2"))
        self.assertEqual(upgraded.inactive, ("abilities:medium_expert",))
        with self.assertRaises(RuleError):
            learn_ability(upgraded, "Small Expert", self.catalog)
        with self.assertRaises(RuleError):
            activate_ability(upgraded, "Small Expert", 0, self.catalog)

    def test_new_abilities_are_inactive_and_inactive_upgrades_stay_inactive(self):
        state = learn_ability(AbilityLoadout(), "Small Expert", self.catalog)
        state = learn_ability(state, "Small Expert 4", self.catalog)
        self.assertEqual(state, AbilityLoadout((), ("abilities:small_expert_4",)))
        self.assertEqual(learn_ability(state, "Small Expert 4", self.catalog), state)

    def test_switching_size_abilities_retains_inactive_ownership(self):
        state = AbilityLoadout(("Small Expert",), ("Medium Expert",))
        with self.assertRaises(RuleError):
            activate_ability(state, "Medium Expert", 1, self.catalog)
        switched = activate_ability(state, "Medium Expert", 0, self.catalog)
        self.assertEqual(switched.active, ("abilities:medium_expert",))
        self.assertEqual(switched.inactive, ("abilities:small_expert",))
        inactive = deactivate_ability(switched, 0, self.catalog)
        self.assertEqual(inactive.active, (None,))
        self.assertEqual(len(inactive.inactive), 2)

    def test_duplicate_family_across_active_and_inactive_rejected(self):
        with self.assertRaises(RuleError):
            validate_loadout(AbilityLoadout(("Small Expert",), ("Small Expert 2",)), self.catalog)

    def test_general_rank_rules_cover_numbered_unnumbered_and_source_spelling(self):
        for lower, higher in (("Lion Type 1", "Lion Type 2"), ("Melee Expert", "Melee Expert 2"), ("Fleet Footed", "FLeet Footed 4")):
            with self.subTest(family=lower):
                state = learn_ability(AbilityLoadout((lower,)), higher, self.catalog)
                self.assertEqual(state.active, (self.catalog.find("abilities", higher)["id"],))
                with self.assertRaises(RuleError):
                    learn_ability(state, lower, self.catalog)

    def test_unowned_activation_and_invalid_slots_rejected(self):
        with self.assertRaises(RuleError):
            activate_ability(AbilityLoadout(), "Small Expert", 0, self.catalog)
        with self.assertRaises(RuleError):
            activate_ability(AbilityLoadout((), ("Small Expert",)), "Small Expert", 6, self.catalog)


if __name__ == "__main__":
    unittest.main()
