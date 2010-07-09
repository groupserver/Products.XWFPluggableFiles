# Copyright (C) 2003,2004 IOPEN Technologies Ltd.
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# You MUST follow the rules in http://iopen.net/STYLE before checking in code
# to the trunk. Code which does not follow the rules will be rejected.  
#
import os

from zope.interface import Interface

from Products.PageTemplates.PageTemplateFile import PageTemplateFile

from AccessControl import getSecurityManager, ClassSecurityInfo
from App.class_init import InitializeClass
from OFS.Image import File

from Products.XWFCore.XWFCatalogAware import XWFCatalogAware
from Products.XWFCore.XWFUtils import convertTextToAscii, removePathsFromFilenames
from Products.XWFContentFramework.XWFDataObject import XWFDataObject

from ComputedAttribute import ComputedAttribute
from ZPublisher.HTTPRequest import FileUpload

from types import * #@UnusedWildImport

from zLOG import LOG, INFO

class IXWFPluggableFileStorage( Interface ):
    """ Interface for a pluggable file storage.
    
    """
    def set_physicalPath( physical_path ):
        """ This enables the base file class to set the physical
            path in ZODB to the file metadata when the file is added,
            moved, or copied.
            
        """
        
    def write( file_object ):
        """ Write data to the storage, in one go.
            
            Returns: None
        """
        
    def read():
        """ Read data from the storage, in one go.
        
        """

class IXWFFileReader( Interface ):
    """ Interface for returning the data and size from a
    file or string.
    
    """
    def set_physicalPath():
        """ Takes a physical path tuple.
        
        """
    
    def reader( file_or_string ):
        """ Takes a file or string, and return the data and 
        size.
        
            Returns: data, size
        """
        

class XWFZODBFileStorage:
    __implements__ = ( IXWFPluggableFileStorage, )
    def __init__( self ):
        self.__data = ''
        
    def write( self, file_object ):
        if isinstance( file_object, StringType ):
            self.__data = file_object
        elif hasattr( file_object, 'data' ):
            # it's probably the built in file object type
            self.__data = file_object.data
        else:
            
            self.__data = file_object.read()
        
    def read( self ):
        return self.__data

class XWFFileSystemFileStorage:
    __implements__ = ( IXWFPluggableFileStorage, IXWFFileReader )
    
    baseFileStoragePath = '/home/richard/filestorage/'
    
    def __init__( self ):
        self.physicalPath = ''
    
    def set_physicalPath( self, physical_path ):
        if self.physicalPath != physical_path and self.physicalPath:
            if physical_path:
                self.rename( physical_path )
            else:
                self.remove()
            
        self.physicalPath = physical_path
    
    def __file_path( self, physical_path ):
        base_path = self.baseFileStoragePath
        path = os.path.join( base_path, 
                             '/'.join( filter( None, physical_path ) ) )
        return path
        
    def open_file( self, flags ):
        path = self.__file_path( self.physicalPath )
        if not os.path.exists( os.path.split( path )[0] ):
            os.makedirs( os.path.split( path )[0] )
        
        f = file( path, flags )
        
        return f
    
    def rename( self, new ):
        old_path = self.__file_path( self.physicalPath )
        new_path = self.__file_path( new )
        if not os.path.exists( os.path.split( new_path )[0] ):
            os.makedirs( os.path.split( new_path )[0] )
        os.rename( old_path, new_path )
        
    def remove( self ):
        old_path = self.__file_path( self.physicalPath )
        os.remove( old_path )
        
    def reader( self, file_or_string ):
        if isinstance( file_or_string, StringType ):
            return file_or_string, len( file_or_string )
        
        elif isinstance( file_or_string, FileUpload ) and not file_or_string:
            raise ValueError, 'File not specified'
        
        file_or_string.seek( 0, 2 )
        size = file_or_string.tell()
        file_or_string.seek( 0 )
        
        return file_or_string.read(), size
    
    def write( self, file_object ):
        if not self.physicalPath:
            return # we haven't been setup yet
            
        f = self.open_file( 'wb+' )
        if isinstance( file_object, StringType ):
            f.write( file_object )
        elif hasattr( file_object, 'data' ):
            # it's probably the built in file object type
            f.write( file_object.data )
        else:
            f.write( file_object.read() )
        
    def read( self ):
        if not self.physicalPath:
            return # we haven't been setup yet
        
        try:
            f = self.open_file( 'rb' )
        except:
            return ''
        
        return f.read()
        
storage_plugins = ( XWFZODBFileStorage, )

class XWFPluggableFile( File, XWFDataObject ):
    """ The basic implementation for a file object, wih metadata stored in 
    the ZODB, and the data stored on disk.
    
    """
    security = ClassSecurityInfo()
    
    meta_type = 'XWF Pluggable File'
    version = 0.1
    
    def __init__( self, id, storage_plugin ):
        """ Initialise a new instance of XWFPluggableFile.
            
        """
        self.storage_plugin = storage_plugin()
        # we do a quick, fake, init here, and do the actual file
        # later
        File.__init__( self, id, id, '' )
        
        security = getSecurityManager()
        self.manage_addProperty( 'dc_creator', security.getUser().getId(), 'ustring' )
        self.manage_addProperty( 'original_filename', '', 'ustring' )
        
    def initialise( self, file_object ):
        if IXWFFileReader.isImplementedBy( self.storage_plugin ):
            self.storage_plugin.set_physicalPath( self.getPhysicalPath() )
        self.manage_upload( file_object )
        self.index_object()
        
    def manage_beforeDelete( self, item, container ):
        """ For cleaning up as we are removed.
        
        """
        if IXWFFileReader.isImplementedBy( self.storage_plugin ):
            self.storage_plugin.set_physicalPath( None )
        XWFCatalogAware.manage_beforeDelete( self, item, container )
        File.manage_beforeDelete( self, item, container )

    def manage_afterAdd( self, item, container ):
        """ For cleaning up as we are removed.
        
        """
        File.manage_afterAdd( self, item, container )
        if IXWFFileReader.isImplementedBy( self.storage_plugin ):
            self.storage_plugin.set_physicalPath( self.getPhysicalPath() )
        XWFCatalogAware.manage_afterAdd( self, item, container )
    
    def manage_afterClone( self, item ):
        """ For configuring the object post copy.
        
        """
        File.manage_afterClone( self, item )
        if IXWFFileReader.isImplementedBy( self.storage_plugin ):
            self.storage_plugin.set_physicalPath( self.getPhysicalPath() )
        XWFCatalogAware.manage_afterClone( self, item )
    
    def write( self, file_object ):
        """ Write the file data to our backend, given an object with a 'file'
        like interface, or a string.
        
        """
        LOG('XWFPluggableFile2.1',INFO,str(dir(file_object)))
        #return self.storage_plugin.write( file_object )
        
    def update_data( self, data, content_type=None, size=None ):
        if content_type is not None: self.content_type=content_type
        if size is None: size=len( data )
        self.size=size
        self.write( data )
        self.ZCacheable_invalidate()
        self.ZCacheable_set( None )
        self.http__refreshEtag()
        self.set_modification_time()
    
    def manage_upload( self, file='', REQUEST=None ):
        """ This overrided the manage_upload provided by the File class
        to add a hook for setting the original filename.
        
        """
        LOG('XWFPluggableFile1.1',INFO,str(dir(file)))
        File.manage_upload( self, file )
        
        filename = getattr( file, 'filename', '' )
        filename = convertTextToAscii( removePathsFromFilenames( filename ) )
        
        self.filename = filename
        self.manage_changeProperties(original_filename=filename)\
        
        if REQUEST:
            message="Saved changes."
            return self.manage_main( self, REQUEST, manage_tabs_message=message )
    
    def _read_data( self, file ):
        if IXWFFileReader.isImplementedBy( self.storage_plugin ):
            return self.storage_plugin.reader( file )
        
        return File._read_data( self, file )
    
    def read( self ):
        """ Read back the file data from our backend.
            
            This just returns the data, it doesn't do _anything_ tricky,
            like setting HTTP headers, or getting ranges from the file.
        
        """
        return self.storage_plugin.read()
    
    data = ComputedAttribute( read )

    def set_content( self, content ):
        self.update_data( content )
        
    def indexable_content( self ):
        return self.read()

    def indexable_summary( self ):
        return self.read()[:200]
    
    def get_filename( self ):
        """ A hook for getting a filename for the file, when it is downloaded.
        
        This can be overridden to produce useful names in different situations.
        
        """
        filename = self.getProperty( 'original_filename', '' )
        if not filename:
            filename = self.getProperty( 'title' )
            
        if filename:
            filename = filename.strip()
            
        return filename
        
    def index_html( self, REQUEST, RESPONSE ):
        """ Extends the file index_html to set the download filename.
        
        """
        filename = self.get_filename()
        REQUEST.RESPONSE.setHeader( 'Content-Disposition', 
                                   'inline; filename="%s"' % filename )
        
        return File.index_html( self, REQUEST, RESPONSE )
    
    
InitializeClass( XWFPluggableFile )
#
# Zope Management Methods
#
manage_addXWFPluggableFileForm = PageTemplateFile( 
    'management/manage_addXWFPluggableFileForm.zpt', 
    globals(), __name__='manage_addXWFPluggableFileForm' )

def manage_addXWFPluggableFile( container, id, file_object, 
                             REQUEST=None, RESPONSE=None, submit=None ):
    """ Add a new instance of XWFPluggableFile.
        
    """
    # we do this in two stages. We can't use the storage plugin until we
    # have a context in the file system
    obj = XWFPluggableFile( id, XWFZODBFileStorage )
    container._setObject( id, obj )
    
    obj = getattr( container, id )
    obj.initialise( file_object )
    
    if RESPONSE and submit:
        if submit.strip().lower() == 'add':
            RESPONSE.redirect( '%s/manage_main' % container.DestinationURL() )
        else:
            RESPONSE.redirect( '%s/manage_main' % id )

def initialize( context ):
    context.registerClass( 
        XWFPluggableFile, 
        permission='Add XWF File', 
        constructors=( manage_addXWFPluggableFileForm, 
                      manage_addXWFPluggableFile ), 
        icon='icons/ic-filestorage.png'
        )

