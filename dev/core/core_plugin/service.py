def get_changelog():
    file_path = 'dev/varibles/changelog.txt'
    build = None
    name = None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if "BUILD" in line and build is None:
                    build = line.split("BUILD")[1].strip(" | \n")
                if "NAME" in line and name is None:
                    name = line.split("NAME")[1].strip(" | \n")
                if build and name:
                    break
            bot_version = f"{build} - {name}" if build and name else "Unknown"
        return file_path, bot_version
    except Exception as e:
        return None, str(e)