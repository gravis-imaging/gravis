import sys, os

import mra


def main():

    
    object = mra.MRA(os.environ)

    ret_code = object.calculateMIPs()
    sys.exit(ret_code.value)


if __name__ == "__main__":
    main()
