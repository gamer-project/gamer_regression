import h5py


class hdf_info_read:
    def __init__(self, file_name):
        self.file_name = file_name
        hdf_file = h5py.File(file_name, 'r')
        self.gitBranch = hdf_file['Info']['KeyInfo']['GitBranch']
        self.gitCommit = hdf_file['Info']['KeyInfo']['GitCommit']
        self.DataID = hdf_file['Info']['KeyInfo']['UniqueDataID']

        self.GridData = self.__loadGridData(hdf_file)
        self.ParticleData = self.__loadParticleData(hdf_file)

    def __loadGridData(self, hdf_file):
        if 'GridData' in hdf_file.keys():
            return hdf_file['GridData']
        else:
            return None

    def __loadParticleData(self, hdf_file):
        if 'Particle' in hdf_file.keys():
            return hdf_file['Particle']
        else:
            return None


# Simple test
if __name__ == '__main__':
    f = hdf_info_read('./tests/MHD_ABC/MHD_ABC_input1/Data_000000')

    print(f.DataID)
    print(f.gitBranch)
    print(f.gitCommit)

    print(f.GridData)
    print(f.ParticleData)
