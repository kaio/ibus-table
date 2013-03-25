__all__ = (
    "itdebug",
)
import traceback
import inspect
def lineno(offset=3):
    """Returns the current line number in our program."""
    frame = inspect.currentframe()
    for i in range(0, offset):
        frame = frame.f_back
    return "%s.%s" %(inspect.getframeinfo(frame).filename,frame.f_lineno)

class itdebug():
    def defin(self, param=''):
        if param:
            param=" (%s)" %param
        if not 'def_depth' in dir(self):
            self.def_depth = 1
        print "%s%s.%s%s from %s" %(' '*self.def_depth, self.__class__.__name__, traceback.extract_stack(limit=2)[-2][2], param, lineno())
        self.def_depth = self.def_depth + 1 
    
    def definfo(self,param=''):
        if param:
            print "%s%s line %s" %(' '*self.def_depth, param,lineno(2))
            
    def defout(self, param=''):
        self.def_depth = self.def_depth - 1
        if param:
            print "%s%s.%s returns %s" %(' '*self.def_depth, self.__class__.__name__, traceback.extract_stack(limit=2)[-2][2], param)