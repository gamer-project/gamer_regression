import h5py


class hdf_info_read:
    def __init__(self, file_name):
        self.file_name    = file_name
        hdf_file          = h5py.File(file_name,'r')
        self.gitBranch    = hdf_file['Info']['KeyInfo']['GitBranch']
        self.gitCommit    = hdf_file['Info']['KeyInfo']['GitCommit']
        self.DataID       = hdf_file['Info']['KeyInfo']['UniqueDataID']

#Simple test
if __name__ == '__main__':
    f = hdf_info_read('../tests/Riemann/Data_000010')

    print(f.DataID)
    print(f.gitBranch)
    print(f.gitCommit)
