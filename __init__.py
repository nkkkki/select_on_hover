def classFactory(iface):  # required by QGIS
    from .select_on_hover import SelectOnHoverPlugin
    return SelectOnHoverPlugin(iface)
