from io import BytesIO
import pandas as pd


def export_plan(courses, schedule):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        courses.to_excel(writer, index=False, sheet_name="推荐课程")
        schedule.to_excel(writer, index=False, sheet_name="课程安排")
    bio.seek(0)
    return bio.getvalue()
