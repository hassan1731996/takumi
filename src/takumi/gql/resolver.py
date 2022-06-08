from graphene.types.resolver import set_default_resolver


def default_resolver(attname, default_value, root, info, **kwargs):
    """A default resolver that handles objects and dictionaries

    To prevent the resolver from swallowing AttributeError from deep within the
    object, we check if the attribute name is in the list of attribute names of
    the object.

    Using `hasattr` simply calls `getattr` and checks if an AttributeError was
    thrown, meaning that if something throws an AttributeError further down the
    stack, the error is swallowed and `getattr` simply returns `False`.
    """
    if isinstance(root, dict):
        return root.get(attname, default_value)
    if attname not in dir(root):
        return default_value

    attr = getattr(root, attname)
    if callable(attr):
        return attr()
    return attr


set_default_resolver(default_resolver)
