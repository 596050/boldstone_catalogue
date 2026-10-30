"""Count overlapping identity scopes separately from accepted proposal groups."""


def identity_counts(user):
    parent = user.get('decisions', [])
    finish = user.get('size_finish_variant_decisions', [])
    builds = user.get('build_variant_decisions', []) + user.get('build_variant_identity_decisions', [])
    layouts = user.get('component_layout_identity_decisions', [])
    counts = dict(user.get('identity_confirmation_counts', {}))
    counts.update({
        'component_designs': len({x['component_id'] for x in parent}),
        'explicit_size_finish_variant_names': len({(x['component_id'], x['size_finish_variant_id']) for x in finish if x.get('identity_confirmed')}),
        'explicit_build_variant_decisions': len({(x['component_id'], x['build_variant_id']) for x in builds}),
        'explicit_component_layout_names': len({(x['component_id'], x['component_layout_id']) for x in layouts if x.get('identity_confirmed')}),
        'components_with_any_identity_scope': len({x['component_id'] for seq in [parent, finish, builds, layouts] for x in seq}),
    })
    return counts


def specification_counts(user):
    parent = user.get('specification_decisions', [])
    builds = user.get('build_variant_decisions', [])
    finishes = user.get('size_finish_variant_specification_decisions', [])
    groups = lambda rows: len({p for x in rows for p in x.get('approved_proposal_ids', [])})
    a, b, c = (groups(rows) for rows in [parent, builds, finishes])
    return {
        'components': len({x['component_id'] for x in parent}),
        'component_proposal_groups': a,
        'build_variant_approvals': len({(x['component_id'], x['build_variant_id']) for x in builds if x.get('proposals_approved')}),
        'build_variant_proposal_groups': b,
        'size_finish_variant_approvals': len({(x['component_id'], x['size_finish_variant_id']) for x in finishes if x.get('proposals_approved')}),
        'size_finish_variant_proposal_groups': c,
        'proposal_groups': a + b + c,
    }
