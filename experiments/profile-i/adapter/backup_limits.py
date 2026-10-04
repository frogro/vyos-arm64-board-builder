"""Validate expanded backup size before upstream restore writes any files."""
import os,tarfile,shutil
from pathlib import Path
from storage_guard import GIB,used_bytes

def install():
    from anthias_server.lib import backup_helper as helper
    if getattr(helper.recover,'_vyarm_bounded',False):return
    from backup_settings import add_settings, read_settings, host_request
    if hasattr(helper, '_add_manifest'):
        original_manifest=helper._add_manifest
        def manifest(tar):
            original_manifest(tar)
            add_settings(tar)
        helper._add_manifest=manifest
    original=helper.recover
    def recover(path):
        root=Path(os.environ.get('HOME','/data'))
        limit=int(os.getenv('I_STORAGE_LIMIT_BYTES',str(8*GIB)))
        reserve=int(os.getenv('I_FREE_RESERVE_BYTES',str(GIB)))
        total=0;count=0
        with tarfile.open(path,'r:gz') as archive:
            try: settings=read_settings(archive)
            except (ValueError, TypeError, KeyError) as error: raise helper.BackupRecoverError(str(error)) from error
            for member in archive:
                count+=1
                if count>100000:raise helper.BackupRecoverError('Backup contains too many entries')
                if helper._safe_tar_member(member,str(root)) and member.isfile():
                    total+=member.size
                    if total>limit:raise helper.BackupRecoverError('Expanded backup exceeds media storage limit')
        # Conservative: retain space for current files and a complete restored copy.
        if used_bytes(root)+total>limit or shutil.disk_usage(root).free<reserve+total:
            raise helper.BackupRecoverError('Insufficient space to restore backup safely')
        result=original(path)
        if settings is not None:
            try: host_request('apply', settings)
            except Exception as error:
                raise helper.BackupRecoverError('Media restored, but display settings could not be applied: '+str(error)) from error
        return result
    recover._vyarm_bounded=True
    helper.recover=recover
