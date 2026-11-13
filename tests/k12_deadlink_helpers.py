"""K12-NJ-DEADLINK-001: the Edison Twp contract URL changed after the base commits other tests compare against.
`undo` maps a current page/file back to its pre-ticket text so those comparisons stay exact; `FILES` are the two committed files that differ from the base."""
OLD_URL = "https://5il" ".co/2u0cp"
NEW_URL = ("https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/4500/Eps/"
           "7025b86b-a5ce-4996-9ba2-429cad8337e7/ETEA-Certified-Contract-July-2023-June-2028.pdf")
FILES = ("api/v1/nj/3404500.json", "nj/history/index.html")  # plus nj/edison-twp-3404500/index.html, a district page


def undo(text):
    text = text.replace(f"{NEW_URL}\">{NEW_URL.rsplit('/', 1)[1]}</a>", f"{OLD_URL}\">{OLD_URL.rsplit('/', 1)[1]}</a>")
    return text.replace(NEW_URL, OLD_URL)
