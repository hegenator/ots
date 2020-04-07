def ensure_attribute(iterable, attribute, default):
    """
    Ensures that all instances of all objects in `iterable` have
    an attribute `attribute`m ny setting that attribute with a default
    value `default` if the attribute doesn't exist yet.
    :param iterable: Any iterable of any objects
    :param attribute: Name of the attribute
    :param default: Default value to assign
    :return: None
    """
    for i in iterable:
        if not hasattr(i, attribute):
            setattr(i, attribute, default)
