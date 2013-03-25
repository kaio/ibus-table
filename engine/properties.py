__all__ = (
    "properties",
)
import os
import types
import itdebug
from common_functions import *

from copy import deepcopy;
from gi.repository import IBus
from gi.repository import GLib
 

class properties(IBus.Engine, itdebug.itdebug):
    def __init__(self, iBus, obj_path, table_db, _table_properties):
        super(properties,self).__init__ (connection=iBus.get_connection(),
                                        object_path=obj_path)
        self.db = table_db
        
        self.def_depth=1        
        _name=self.db.get_ime_property('name')
   
        self._icon_dir = '%s%s%s%s' % (os.getenv('IBUS_TABLE_LOCATION'),
            os.path.sep, 'icons', os.path.sep)
        self._config_section = "engine/Table/%s" % _name.replace(' ', '_')
        self._config = iBus.get_config ()
        self._config.connect ("value-changed", self._ime_config_value_changed)

        _table_properties['engine-mode'] = {
                   'label': ['Keyboard mode', 'status_prompt'],
                   'tooltip': ['Switch to table mode','Switch to keyboard mode'],
                   'value': 1,
                   'user-configurable': True,
                   'engine-mode-dependant': False,
                   'menu-index': 1,
                   'shift-callback': self._callback_engine_mode
           }
        _table_properties['engine-mode']['label'][1] = self.db.get_ime_property('status_prompt')
        _table_properties['engine-mode']['icon'] = ['ibus-keyboard.svg', self.db.get_ime_property('icon')]

        self.init_table_properties(_table_properties)

    def init_table_properties (self, properties):
        '''
        Initializes the table properties using the provided dict's properties.
        '''
        self._table_properties=properties
        for property_name in properties.keys():
            if not property_name.startswith('_'):
                __property=self.init_table_property(property_name, properties[property_name]['value'], properties[property_name]['user-configurable'])
                if 'engine-mode-dependant' in __property.keys() and __property['engine-mode-dependant'] == True:
                    for i in [0,1]:
                        properties['%s_%d' %(property_name,i)]=deepcopy(__property)
                        properties['%s_%d' %(property_name,i)]['engine-mode-dependant-child']=True
                        self.init_table_property('%s_%d' %(property_name, i), __property['value'], __property['user-configurable'])
                    __property['value'] = self._table_properties["%s_%d"%(property_name, int(self._table_properties['engine-mode']['value']))]['value']
    
    def init_table_property (self, property_name, default_value, default_user_configurable=True):
        '''
        Consider the property user-configurable
        
            if usr_%property_name% is found in table DB and set to "true"
        
        Set property's value
        
            if the property can be found as :
         
             - %property_name% in iBus config DB
             - def_%property_name% in table db ime properties
             - %property_name% in table db ime properties (for backward compatibility)
             - %default_value%
        
        Set instance's _table_properties and ibus config DB accordingly
        
        '''
        _table_property=self._table_properties[property_name]
        _user_configurable = self.db.get_ime_property('usr_%s' %property_name)
        if _user_configurable == None or _user_configurable.lower() == u'none':
            _user_configurable = default_user_configurable
        else:
            # Defaults to True
            _user_configurable = not _user_configurable.lower() == u'false'
        _table_property['user-configurable'] = _user_configurable
        _value = variant_to_value(self._config.get_value(self._config_section, property_name))
        if _value == None:
            _value = self.db.get_ime_property('def_%s' %property_name)
            if _value != None:
                if _value.lower() == u'true':
                    _value = True                
                elif _value.lower() == u'false':
                    _value = False
                if isinstance(_value, str):
                    _value=_value.encode('utf8')
            else: # Backward compatibility
                _value = self.db.get_ime_property('%s' %property_name)
                if _value == None or _value.lower() == u'none':
                   _value = default_value
                else:
                    _value = _value.lower() == u'true'
            self._config.set_value(
                self._config_section,
                property_name,
                value_to_variant(_value)
            )
        _table_property['value'] = _value
        
        return _table_property

    def init_ime_properties (self):
        _ime_properties = IBus.PropList ()
        for _table_property in sorted(self._table_properties.iteritems(), key=lambda _tp: _tp[1]['menu-index']):
            _property_name=_table_property[0]
            _table_property=self._table_properties[_property_name]
            if 'visible' not in _table_property.keys():
                _table_property['visible'] = _table_property['user-configurable'] and not 'engine-mode-dependant-child' in _table_property.keys()
                
            if 'sensitive' not in _table_property.keys():
                _table_property['sensitive'] = not 'engine-mode' in _table_property.keys() or _table_property['engine-mode'] == self._table_properties['engine-mode']['value']
            
            _table_property['property'] = IBus.Property(key=u'%s' %_property_name,
                                                        label=None,
                                                        icon=None,
                                                        tooltip=None,
                                                        sensitive=_table_property['sensitive'],
                                                        visible=_table_property['visible'])
            _ime_properties.append(_table_property['property'])
        self.register_properties (_ime_properties)
        self.refresh_user_properties ()
        
    def refresh_user_properties(self):
        for property_name in self._table_properties.keys():
            if self._table_properties[property_name]['user-configurable']:
                self.refresh_user_property (property_name)
        
    def refresh_user_property (self, property_name):
        if property_name in self._table_properties.keys():
            __table_property=self._table_properties[property_name]
            if 'user-configurable' in __table_property.keys() and __table_property['user-configurable'] and 'visible' in  __table_property.keys() and __table_property['visible']:
                if 'icon' in __table_property.keys():
                    icon=__table_property['icon'][int(__table_property['value'])]
                else:
                    icon='%s_%d.svg' %(property_name, int(__table_property['value']))
                __table_property['sensitive'] = not 'engine-mode' in __table_property.keys() or __table_property['engine-mode'] == self._table_properties['engine-mode']['value']
                __ime_property=self._table_properties[property_name]['property']
                __ime_property.set_icon ( u'%s%s' % (self._icon_dir, icon) )
                __ime_property.set_label (IBus.Text.new_from_string(unicode(__table_property['label'][int(__table_property['value'])])))
                __ime_property.set_tooltip (IBus.Text.new_from_string(unicode(__table_property['tooltip'][int(__table_property['value'])])))
                __ime_property.set_sensitive (__table_property['sensitive'])
                self.update_property(__table_property['property'])

    def get_value (self, property_name):
        if property_name in self._table_properties.keys():
            #print "getvalue for %s : %s" %(property_name,self._table_properties[property_name]['value'])
            return self._table_properties[property_name]['value']
        else:
            return None

    def shift_property_value (self, property_name, prop_state = IBus.PropState.UNCHECKED):
        __property=self._table_properties[property_name]
        
        # process mode-dependant childs
        if __property and __property['engine-mode-dependant'] and not 'engine-mode-dependant-child' in __property.keys():
            self.shift_property_value("%s_%d"%(property_name, int(self._table_properties['engine-mode']['value'])))
        
        if __property and __property['user-configurable']:
            __value=__property['value']
            if isinstance(__value, bool):
                # change bistable state
                __value = not __value                                  
            elif isinstance(__value, int): 
                if 'label' in __property.keys() and isinstance(__property['label'], list):
                    # circular iteration among label indexes
                    __value = (__value + 1) % len(__property['label'])
            self._config.set_value( self._config_section,
                    property_name,
                    value_to_variant(__value))
            
            __property['value']=__value
            if 'shift-callback' in __property.keys() and isinstance(__property['shift-callback'], types.MethodType):
                __property['shift-callback'](property_name,__property['value'])
                
            self.refresh_user_property(property_name)
        return __property['value']

    def _ime_config_value_changed (self, config, section, property_name, value):
        self.defin("%s: %s" %(property_name, value))
        #print "config_value %s changed_db to %s." %(property_name, value)
        if property_name in self._table_properties.keys():
            __property=self._table_properties[property_name]
            __property['value'] = variant_to_value(value)
            self.refresh_user_property(property_name)
            if 'shift-callback' in __property.keys() and isinstance(__property['shift-callback'], types.MethodType):
                __property['shift-callback'](property_name, __property['value'])
        self.defout()

    def _callback_engine_mode(self, property_name, value):
        for property_name in self._table_properties.keys():
            __property=self._table_properties[property_name]
            if __property['engine-mode-dependant'] and 'engine-mode-dependant-child' not in __property.keys():
                __property['value'] = self._table_properties["%s_%d"%(property_name, int(self._table_properties['engine-mode']['value']))]['value']
        self.refresh_user_properties()

    # for further implementation :)
    @classmethod
    def CONFIG_VALUE_CHANGED(cls, bus, section, name, value):
        self.definfo()
        config = bus.get_config()
        if section != self._config_section:
            return

    @classmethod
    def CONFIG_RELOADED(cls, bus):
        config = bus.get_config()
        if section != self._config_section:
            return
