from gi.repository import GLib

def variant_to_value(variant):
    if type(variant) != GLib.Variant:
        return variant
    type_string = variant.get_type_string()
    if type_string == 's':
        return variant.get_string()
    elif type_string == 'i':
        return variant.get_int32()
    elif type_string == 'b':
        return variant.get_boolean()
    elif type_string == 'a':
        a=variant.get_array()
        r=[]
        t=a[0]
        for i in a[1]:
            r.append(variant_to_value(i))
        return r
    elif type_string == 'as':
        # In the latest pygobject3 3.3.4 or later, g_variant_dup_strv
        # returns the allocated strv but in the previous release,
        # it returned the tuple of (strv, length)
        if type(GLib.Variant.new_strv([]).dup_strv()) == tuple:
            return variant.dup_strv()[0]
        else:
            return variant.dup_strv()
    else:
        print 'error: unknown variant type:', type_string
        return None
    return variant

def value_to_variant(value):
    if type(value) == GLib.Variant:
        return value
    if isinstance(value, bool):
        return GLib.Variant.new_boolean(value)
    elif isinstance(value, int):
        return GLib.Variant.new_int32(value)
    elif isinstance(value, unicode):
        return GLib.Variant.new_string(value)
    elif isinstance(value, list):
        for v in value:
            v = value_to_variant(v)
        return GLib.Variant.new_array('b',l)
    else:
        print "error : unhandled value type %s" %value.__class__
        exit
    
def argb(a, r, g, b):
    return ((a & 0xff)<<24) + ((r & 0xff) << 16) + ((g & 0xff) << 8) + (b & 0xff)

