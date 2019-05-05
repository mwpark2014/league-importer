import requests
import sys
import tarfile
import traceback

DATA_DRAGON_URL_HTTP = 'https://ddragon.leagueoflegends.com/cdn/dragontail-%s.tgz'
LOCAL_FILENAME = 'data_dragon.tgz'
CHUNK_SIZE = 8192

def initialize_static_tables():
    print('Initializing static data tables...')
    patch_version = get_patch_manual();
    success = get_data_dragon_tarfile(patch_version) # Load file. File will be accessible at LOCAL_FILENAME
    if not success or not tarfile.is_tarfile(LOCAL_FILENAME):
        print('No tables were initialized. Exiting...')
        return


def update_static_tables():
    print('Updating static data tables...')
    return None

def get_patch_manual():
    return input('Please enter desired patch version in X.Y.Z format.\n X=season, Y=major version, Z=minor version\n')

# Return True if successful. False if not.
def get_data_dragon_tarfile(patch_version):
    url = DATA_DRAGON_URL_HTTP % patch_version
    print('Retrieving tar file from Riot Games API: %s...' % url)
    try:
        with requests.get(url, timeout=(3, None), stream=True) as response:
            response.raise_for_status()
            total_length = float(response.headers.get('content-length'))
            with open(LOCAL_FILENAME, "wb") as file:
                # Iterate over chunks
                length_written = 0
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk: # filter out keep-alive new chunks
                        file.write(chunk)
                        length_written += len(chunk)
                        # If we have a content-length header, show progress bar
                        if total_length is not None and length_written % (CHUNK_SIZE * 8) == 0:
                            sys.stdout.write("\r%d%%" % int(length_written / total_length * 100))
                            sys.stdout.flush()
        print()
        return True

    except Exception as err:
        print('Exception encountered when retrieving Riot Data Dragon tar file: %s', str(err))
        traceback.print_tb(err.__traceback__)
        return False

if __name__ == '__main__':
    initialize_static_tables()