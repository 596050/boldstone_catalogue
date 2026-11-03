from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from costing import DEFAULTS, calculate, dimensions, finish_defaults, default_inputs, product_cost, pricing, validate_inputs, validate_settings
from server import Application
from store import ReviewStore, Conflict
from projection import Projection


class CostModelTests(unittest.TestCase):
    def setUp(self):
        self.config = deepcopy(DEFAULTS)
        self.inputs = {'width_cm': 20, 'height_cm': 35, 'depth_cm': 6, 'shape_factor': 1,
                       'casting_factor': 1, 'material': 'gfrc', 'finishes': [{'id':'verdigris','coverage':1}],
                       'fixing_count': 1, 'labour_hours_override': None, 'other_cost': 0, 'notes': ''}

    def test_owner_reference_and_separate_labour(self):
        c=calculate(self.inputs,self.config)
        self.assertEqual([c[k] for k in ('material_cost','finish_cost','fixing_cost','overhead_cost')],[5,5,5,5])
        self.assertEqual(c['subtotal_before_labour'],20)
        self.assertEqual(c['manufacturing_cost'],20)
        self.assertEqual(c['labour_cost'],18.33)
        self.assertEqual(c['total_cost'],38.33)

    def test_labour_override_changes_total_but_not_manufacturing(self):
        for hours, total in [(0, 20), (2, 60), (3.25, 85)]:
            cost = calculate({**self.inputs, 'labour_hours_override': hours}, self.config)
            self.assertEqual(cost['manufacturing_cost'], 20)
            self.assertEqual(cost['total_cost'], total)
            self.assertEqual(pricing({**self.inputs, 'pricing_mode': 'markup'}, self.config,
                                     cost['total_cost'])['marked_up_price'], total * 2)

    def test_large_ammonite_material_costs_and_markup_prices(self):
        inputs={**self.inputs,'width_cm':120,'height_cm':60,'depth_cm':6,
                'finishes':[{'id':'white','coverage':1}],'fixing_count':2,'pricing_mode':'markup'}
        for material,total,selling in [('gfrc',112.87,225.74),('jesmonite',321.57,643.14)]:
            with self.subTest(material=material):
                scenario={**inputs,'material':material}
                cost=calculate(scenario,self.config)
                self.assertEqual(cost['total_cost'],total)
                self.assertEqual(pricing(scenario,self.config,cost['total_cost'])['marked_up_price'],selling)

    def test_half_penny_rounding_is_stable_after_volume_arithmetic(self):
        inputs={**self.inputs,'width_cm':31.5,'height_cm':31.5,'depth_cm':4}
        self.assertEqual(calculate(inputs,self.config)['material_cost'],4.73)
        self.assertEqual(calculate({**inputs,'material':'moulding_paste'},self.config)['material_cost'],93.56)

    def test_white_is_uncoloured_and_independent_labour_override(self):
        c=calculate({**self.inputs,'finishes':[{'id':'white','coverage':1}], 'labour_hours_override':0},self.config)
        self.assertEqual(c['finish_cost'],0);self.assertEqual(c['total_cost'],15)
        c=calculate({**self.inputs,'labour_hours_override':2},self.config)
        self.assertEqual(c['total_cost'],60)

    def test_dimensions_circle_ranges_and_individual_not_arrangement(self):
        self.assertEqual(dimensions('35 x 35 cm per panel; approximately 6 cm deep; arrangement 70 x 70 cm'),(35,35,6,1))
        self.assertEqual(dimensions('55 cm high x 30 cm wide x 5–7 cm deep'),(30,55,6,1))
        self.assertEqual(dimensions('6 cm deep × 40 cm wide × 45 cm high'),(40,45,6,1))
        self.assertEqual(dimensions('45–60 cm square; 10–18 cm overall height'),(52.5,52.5,14,1))
        circle=dimensions('50 cm diameter x 2.5 cm deep');self.assertEqual(circle[:3],(50,50,2.5));self.assertAlmostEqual(circle[3],.7853981633974483)
        with self.assertRaises(ValueError): dimensions('Unknown')

    def product(self,dim='35 x 20 x 6 cm',name='Panel White',fix='Keyhole or French cleat',weight='4 kg'):
        fields=[{'key':k,'value':v} for k,v in [('Name',name),('Dimensions / depth',dim),('Fixing',fix),('Weight',weight),('Material / finish','Plaster')]]
        return {'id':'A','name':name,'family':'Panels','fields':fields}

    def test_one_fixing_for_both_reference_and_30_square_more_for_large(self):
        for dim in ('35 x 20 x 6 cm','30 x 30 x 6 cm'):
            self.assertEqual(default_inputs(self.product(dim),[])['fixing_count'],1)
        self.assertEqual(default_inputs(self.product('50 x 30 x 6 cm'),[])['fixing_count'],2)
        self.assertEqual(default_inputs(self.product('250 x 100 x 8 cm'),[])['fixing_count'],8)

    def test_hollow_body_uses_mass_not_solid_envelope(self):
        p=self.product('100 x 100 cm fountain block; 50 cm body depth',fix='Freestanding',weight='100 kg dry')
        i=default_inputs(p,[]);c=calculate(i,self.config)
        self.assertEqual(i['fixing_count'],0);self.assertAlmostEqual(c['casting_scale'],25)
        self.assertEqual(c['material_cost'],125)

    def test_combined_finishes_are_not_double_counted(self):
        self.assertEqual(finish_defaults('Dune Verdigris and Copper',''),[{'id':'verdigris','coverage':1}])
        finishes=finish_defaults('Dune Verdigris and Rust','')
        self.assertEqual(sum(f['coverage'] for f in finishes),1)
        self.assertEqual(calculate({**self.inputs,'finishes':finishes},self.config)['finish_cost'],5)

    def test_genuine_and_imitation_gold_are_distinct(self):
        self.assertEqual(finish_defaults('Acanthus Gold Leaf','Plaster with gold leaf')[0]['id'],'gold_imitation')
        self.assertEqual(finish_defaults('Leaf White and Gold Leaf','Gold-leaf-effect')[0],{'id':'gold_imitation','coverage':.5})
        self.assertEqual(finish_defaults('Panel Gold','Genuine gold leaf')[0]['id'],'gold_imitation')
        saved={'kind':'cost','product_id':'A','item_id':'','version':1,
               'data':{**self.inputs,'finishes':[{'id':'gold_genuine','coverage':1}]}}
        explicit=product_cost(self.product(name='Panel Gold Leaf'),[saved])
        self.assertEqual(explicit['finish_cost'],46)

    def test_extensible_materials_and_finishes(self):
        self.config['materials']['new_mix']={'label':'New mix','rate':9,'minutes':6,'basis':'Workshop','source':''}
        self.config['finishes']['new_finish']={'label':'New finish','rate':3,'minutes':6,'basis':'Workshop','source':''}
        validate_settings(self.config)
        c=calculate({**self.inputs,'material':'new_mix','finishes':[{'id':'new_finish','coverage':.5}]},self.config)
        self.assertEqual(c['material_cost'],9);self.assertEqual(c['finish_cost'],1.5)

    def test_strict_validation_rejects_nonfinite_negative_missing_and_duplicates(self):
        for key,val in [('width_cm',0),('depth_cm',-1),('shape_factor',float('nan')),('fixing_count',1.5),('other_cost',True),('material','missing')]:
            with self.subTest(key=key),self.assertRaises(ValueError):validate_inputs({**self.inputs,key:val},self.config)
        with self.assertRaises(ValueError):validate_inputs({**self.inputs,'finishes':self.inputs['finishes']*2},self.config)
        bad=deepcopy(self.config);bad['materials']['gfrc']['rate']=float('inf')
        with self.assertRaises(ValueError):validate_settings(bad)

    def test_spec_changes_recalculate_without_overwriting_source(self):
        p=self.product();before=deepcopy(p)
        reviews=[{'kind':'field','product_id':'A','item_id':'Dimensions / depth','data':{'decision':'edit','value':'70 x 20 x 6 cm'}}]
        c=product_cost(p,reviews);self.assertEqual(c['material_cost'],10);self.assertEqual(p,before)

    def test_saved_inputs_override_defaults_and_rate_changes_recalculate(self):
        r={'kind':'cost','product_id':'A','item_id':'','version':1,'data':{**self.inputs,'other_cost':7}}
        self.config['labour_hourly']=30
        s={'kind':'cost_settings','product_id':'','item_id':'','version':2,'data':self.config}
        c=product_cost(self.product(),[r,s]);self.assertEqual(c['total_cost'],54.5)
        self.assertEqual(c['settings_version'],2)

    def test_cost_save_conflicts_are_durable_and_independent_of_other_reviews(self):
        with tempfile.TemporaryDirectory() as d:
            app=Application.__new__(Application);app.store=ReviewStore(d)
            p=self.product();app.catalogue=SimpleNamespace(products={'A':p},assets={},edges={},source={'register_sha256':'source'})
            app.projection=lambda:Projection(app.catalogue,app.store.all())
            body={'kind':'cost','product_id':'A','item_id':'','version':0,'settings_version':0,'data':self.inputs}
            saved=app.save(body);self.assertEqual(saved['version'],1)
            with self.assertRaises(Conflict):app.save(body)
            cfg={'kind':'cost_settings','product_id':'','item_id':'','version':0,'data':self.config}
            app.save(cfg)
            with self.assertRaises(Conflict):app.save({**body,'version':1})
            self.assertEqual(len(app.store.all()),2)
            self.assertEqual(ReviewStore(d).get('cost','A','')['data'],self.inputs)


if __name__=='__main__': unittest.main()
