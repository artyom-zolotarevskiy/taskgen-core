from taskgen.functions import round_n

def DataSet(value):
    return ["DataSet", value]

def Numerical(value, ndigits=None):
    if ndigits is not None:
        value = round_n(value, ndigits)
    return ["Numerical", value]

def Image(value, caption = '', width=r'\textwidth'):
    return ["Image", value, caption, width]