"""Customer-facing values, kept separate from source and review provenance."""


def listing_value(field, choice):
    action = choice.get('decision', 'pending')
    if action == 'exclude':
        return None
    value = choice.get('value', '') if action == 'edit' else field['value']
    # Do not append certainty to copy. It is retained in separate metadata.
    return value.replace('\u2014', '-')
