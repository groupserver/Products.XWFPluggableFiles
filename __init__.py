# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in http://iopen.net/STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
def initialize(context):
    # Import lazily, and defer initialization to the module
    import XWFPluggableFile
    
    XWFPluggableFile.initialize(context)
