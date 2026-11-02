import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from companion_groups import companion_notes, apply_companion_note


class CompanionGroupsTests(unittest.TestCase):
    def product(self, pid, title, image='group', filename='family__one-and-two-white__001.png'):
        return {'id': pid, 'name': title, 'retail_name': title, 'family': 'Family',
                'listing_decision': 'include', 'photos': {'listing': {'images': []},
                'in_situ': {'images': [{'id': image, 'name': filename}]}}}

    def test_finishes_do_not_become_companions_and_variant_inherits_design_relation(self):
        one = self.product('1', 'Panel I - White')
        same = self.product('1b', 'Panel I - Bronze')
        two = self.product('2', 'Panel II - White')
        other = self.product('2b', 'Panel II - Gold', 'individual', 'plain.jpg')
        notes = companion_notes({'products': [one, same, two, other]})
        self.assertEqual(notes['1']['companions'], ['Panel II'])
        self.assertEqual(notes['1b']['companions'], ['Panel II'])
        self.assertEqual(notes['2b']['companions'], ['Panel I'])
        self.assertIn('sold separately', notes['2b']['text'])

    def test_sizes_and_excluded_records_are_kept_separate(self):
        big1 = self.product('b1', 'Grande I - White', 'big')
        big2 = self.product('b2', 'Grande II - White', 'big')
        small1 = self.product('s1', 'Petite I - White', 'small')
        small2 = self.product('s2', 'Petite II - White', 'small')
        unrelated = self.product('x', 'Excluded III - White', 'big')
        unrelated['listing_decision'] = 'exclude'
        notes = companion_notes({'products': [big1, big2, small1, small2, unrelated]})
        self.assertEqual(notes['b1']['companions'], ['Grande II'])
        self.assertEqual(notes['s1']['companions'], ['Petite II'])
        self.assertNotIn('x', notes)
        text = 'Design prose.\n\nQuantity supplied: 1\nMaterial: gypsum'
        updated = apply_companion_note(text, notes['b1'])
        self.assertEqual(apply_companion_note(updated, notes['b1']), updated)
        self.assertEqual(apply_companion_note(updated, None), text)

    def test_reused_individual_photo_or_one_design_is_not_a_pair(self):
        one = self.product('1', 'Panel I - White', filename='individual.jpg')
        two = self.product('2', 'Panel II - White', filename='individual.jpg')
        self.assertEqual(companion_notes({'products': [one, two]}), {})
        one = self.product('1', 'Panel I - White')
        same = self.product('1b', 'Panel I - Bronze')
        self.assertEqual(companion_notes({'products': [one, same]}), {})


if __name__ == '__main__': unittest.main()
