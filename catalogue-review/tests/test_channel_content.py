from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_content import complete_description, marketplace_title, finish_retail_name, product_type, validate, description_html, chairish_description, saatchi_description, surface_variation_copy, has_surface_effect, SURFACE_VARIATION, SURFACE, CUSTOMISATION

class ChannelContentTests(unittest.TestCase):
    def product(self, name='Moon II - White'):
        return {'id':'BSI-ABC', 'name':name, 'retail_name':name,
                'fields':[{'key':'Material / finish','value':'Gypsum-based material with a white finish'},
                          {'key':'Dimensions / depth','value':'100 × 22 cm; approximately 6 cm panel depth'},
                          {'key':'Weight','value':'Approximately 8–10 kg'}],
                'listing_fields':[{'key':'Description','value':'Lunar curves meet a shell-like wave.\n\nMaterial: Made from a gypsum-based material.\nDimensions: 100 × 22 cm; approximately 6 cm panel depth\nProduction lead time: 1–2 weeks\nDelivery: Please contact us for delivery options.'}]}
    def test_copy_preserves_design_and_measurement_qualification(self):
        p=self.product(); text=complete_description(p,'BOLD-ABC')
        self.assertIn('Lunar curves meet',text); self.assertIn('approximately 6 cm',text)
        self.assertIn('Within 10 working days',text); self.assertNotIn('1–2 weeks',text)
        self.assertIn('Quantity supplied: 1',text); self.assertNotIn('Stock:',text)
        self.assertEqual(validate(p,{'description_text':text,'sku':'BOLD-ABC'}),[])
    def test_repeat_does_not_duplicate_fields_and_exception_is_explicit(self):
        p=self.product(); text=complete_description(p,'BOLD-ABC')
        p['listing_fields'][0]['value']=text
        self.assertEqual(complete_description(p,'BOLD-ABC'),text)
        short=complete_description(p,'BOLD-ABC',3)
        self.assertIn('Within 3 working days',short); self.assertNotIn('10 working',short)
    def test_tiktok_has_no_external_contact_delivery_steering(self):
        text=complete_description(self.product(),'BOLD-ABC',channel='tiktok')
        self.assertIn('shown at checkout',text); self.assertNotIn('contact us',text)
    def test_ebay_copy_matches_native_delivery_and_handling(self):
        for days in (3, 10):
            text=complete_description(self.product(),'BOLD-ABC',dispatch_days=days,channel='ebay')
            self.assertIn(f'Within {days} working days',text)
            self.assertIn('charge are shown in this eBay listing',text)
            self.assertNotIn('contact us',text)
    def test_surface_variation_follows_finishes_without_relabelling_white(self):
        p=self.product()
        p['costing']={'inputs':{'finishes':[{'id':'white'}]}}
        self.assertFalse(has_surface_effect(p))
        self.assertNotIn(SURFACE_VARIATION,complete_description(p,'BOLD-ABC'))
        p['costing']['inputs']['finishes']=[{'id':'verdigris'}]
        self.assertTrue(has_surface_effect(p))
        for channel in ('catalogue','ebay','tiktok'):
            text=complete_description(p,'BOLD-ABC',channel=channel)
            self.assertEqual(text.count(SURFACE_VARIATION),1)
            self.assertIn(SURFACE,text)
            self.assertEqual(surface_variation_copy(text,True),text)
            self.assertNotIn(SURFACE_VARIATION,surface_variation_copy(text,False))
            self.assertEqual(validate(p,{'description_text':text,'sku':'BOLD-ABC','surface_effect':True}),[])
            self.assertIn('Missing handmade surface-effect variation statement',validate(p,{
                'description_text':text.replace(SURFACE_VARIATION,''),'sku':'BOLD-ABC','surface_effect':True}))
    def test_water_feature_and_paver_not_mislabelled_wall_sculpture(self):
        p=self.product('Moon II Fountain - White')
        self.assertEqual(product_type(p),'Sculptural water-feature panel')
        self.assertIn('Pump, basin, pipework and installation are not included.',complete_description(p,'BOLD-ABC'))
        self.assertEqual(product_type(self.product('Paver II - Brown')),'Decorative paver panel')
    def test_title_cap_and_html_escape(self):
        title=marketplace_title(self.product('Extra long ' * 15+'White'),80)
        self.assertLessEqual(len(title),80); self.assertTrue(title.startswith('Boldstone ')); self.assertTrue(title.endswith('Wall sculpture'))
        self.assertIn('&lt;script&gt;',description_html('<script>'))

    def test_effect_titles_and_models_say_finish_without_changing_white(self):
        p=self.product('Spiralfish Wave and Tide I - Bronze')
        p['costing']={'inputs':{'finishes':[{'id':'metallic'}]}}
        expected='Spiralfish Wave and Tide I - Bronze Finish'
        self.assertEqual(finish_retail_name(p),expected)
        self.assertEqual(marketplace_title(p),'Boldstone '+expected+' Wall sculpture')
        self.assertIn('Model: '+expected+' (BOLD-ABC)',complete_description(p,'BOLD-ABC'))
        p['retail_name']=expected
        self.assertEqual(finish_retail_name(p),expected)
        p=self.product('Moon II - White')
        p['costing']={'inputs':{'finishes':[{'id':'white'}]}}
        self.assertEqual(finish_retail_name(p),'Moon II - White')

    def test_title_cap_retains_effect_finish_and_distinguishing_colour(self):
        p=self.product('An unusually long botanical relief name repeated several times - Copper and Verdigris')
        p['costing']={'inputs':{'finishes':[{'id':'verdigris'}]}}
        title=marketplace_title(p,80)
        self.assertLessEqual(len(title),80)
        self.assertTrue(title.endswith(' - Copper and Verdigris Finish Wall sculpture'))
    def test_missing_data_is_not_silently_fabricated(self):
        p=self.product(); p['fields']=[]
        self.assertIn('Missing Weight',validate(p,{'description_text':'Material: unknown','sku':''}))
        p['listing_fields'][0]['value']=''
        with self.assertRaises(ValueError): complete_description(p,'BOLD-ABC')
    def test_chairish_prose_preserves_qualified_facts_and_excludes_public_sku(self):
        record={'sku':'BOLD-ABC','product_type':'Wall sculpture','surface_effect':True,
                'description_text':'A flowing relief.\n\nBrand: Boldstone\nModel: Moon (BOLD-ABC)\n'
                'Material: Made from a gypsum-based material.\nSurface effect: A decorative surface effect is applied.\n'
                'Dimensions: 100 × 22 cm; approximately 6 cm deep\nWeight: Approximately 8–10 kg\n'
                'Use: Suitable for outdoor use and indoor display.\nFixings: Keyhole fixings are usually used.\n'
                'Delivery: Please contact us for a quote.'}
        text=chairish_description(record,10)
        self.assertIn('approximately 6 cm deep',text); self.assertIn('approximately 8–10 kg',text)
        self.assertIn('surface effect is applied',text); self.assertIn('10 working days',text)
        self.assertEqual(text.count(SURFACE_VARIATION),1)
        self.assertNotIn('BOLD-ABC',text); self.assertNotIn('Dimensions:',text)
        self.assertNotIn('contact us',text); self.assertNotIn('made in',text.lower())
        record['description_text']=record['description_text'].replace('Surface effect: A decorative surface effect is applied.\n','')
        with self.assertRaises(ValueError): chairish_description(record)

    def test_saatchi_limit_preserves_facts_and_does_not_invent_year(self):
        record={'sku':'BOLD-ABC','product_type':'Sculptural water-feature panel','surface_effect':True,
                'colour':'Verdigris surface effect',
                'description_text':'Lunar curves meet a shell-like wave.\n\n'+('Longer design inspiration. '*30)+
                '\n\nBrand: Boldstone\nMaterial: Made from a gypsum-based material.\n'
                'Surface effect: A decorative surface effect is applied.\n'
                'Dimensions: 100 × 22 cm; approximately 6 cm deep\nWeight: Approximately 8–10 kg\n'
                'Use: Suitable for outdoor use and indoor display.\nFixings: Keyhole fixings are usually used.\n'
                'Supplied as one sculptural panel. Pump, basin, pipework and installation are not included.'}
        text=saatchi_description(record)
        self.assertLessEqual(len(text),1000)
        self.assertEqual(text.count(SURFACE_VARIATION),1)
        for expected in ('Lunar curves', 'Verdigris', 'gypsum-based', 'surface effect is applied',
                         'approximately 6 cm', 'approximately 8–10 kg', '3 working days',
                         'Pump, basin, pipework and installation are not included.'):
            self.assertIn(expected,text)
        self.assertNotIn('2026',text); self.assertNotIn('original edition',text)
        with self.assertRaises(ValueError): saatchi_description(record,limit=60)
        record['colour']=''
        with self.assertRaises(ValueError): saatchi_description(record)

    def test_compact_channel_copy_keeps_companions_commissions_and_exclusions(self):
        p=self.product('Moon II Fountain - Verdigris')
        p['costing']={'inputs':{'finishes':[{'id':'verdigris'}]}}
        p['listing_fields'][0]['value'] += ('\nWeight: Approximately 8–10 kg'
            '\nUse: Suitable for outdoor use and indoor display.'
            '\nFixings: Keyhole fixings are usually used; French cleats are available.')
        description=complete_description(p,'BOLD-ABC')
        note=('Companion pieces: This is one piece of a coordinating pair with Moon I. '
              'Companion sculptures are sold separately; this listing is for one sculpture only.')
        description=description.replace('Material:',note+'\nMaterial:',1)
        record={'sku':'BOLD-ABC','product_type':'Sculptural water-feature panel','surface_effect':True,
                'colour':'Verdigris effect','description_text':description}
        self.assertEqual(description.count(CUSTOMISATION),1)
        prose=chairish_description(record)
        self.assertIn('Moon I',prose)
        self.assertIn(CUSTOMISATION,prose)
        compact=saatchi_description(record)
        self.assertLessEqual(len(compact),1000)
        for text in ('Moon I','sold separately','One sculpture supplied','designer Sally Price','new commissions',
                     'can be customised','will differ from the photographs','approximately 6 cm',
                     'Pump, basin, pipework and installation are not included.'):
            self.assertIn(text,compact)

if __name__=='__main__': unittest.main()
