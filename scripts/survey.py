# Copyright (c) 2025
# Manuel Cherep <mcherep@mit.edu>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import argparse
import dotenv
dotenv.load_dotenv()
import pandas as pd
import requests

API_TOKEN = os.getenv("QUALTRICS_API_KEY")
DATA_CENTER = "mit"
BASE_URL = f"https://{DATA_CENTER}.qualtrics.com/API/v3"
HEADERS = {
    "x-api-token": API_TOKEN,
    "content-type": "application/json"
}


def create_survey(name):
    url = f"{BASE_URL}/surveys"
    response = requests.post(url, headers=HEADERS, json={"name": name})
    return response.json()["result"]["id"]

def create_block(survey_id):
    url = f"{BASE_URL}/survey-definitions/{survey_id}/blocks"
    response = requests.post(url, headers=HEADERS, json={"Type": "Standard"})
    return response.json()["result"]["id"]

def create_question_payload(exp, image_0, image_1):
    html = f"""
    <p>Select the best product from the images</p>
    <table><tr>
      <td><img src="{image_0}" width="300"><br>Left</td>
      <td><img src="{image_1}" width="300"><br>Right</td>
    </tr></table>
    """
    return {
        "QuestionText": html,
        "DataExportTag": f"{exp}",
        "QuestionType": "MC",
        "Selector": "SAVR",  # Single answer vertical
        "Configuration": {
            "QuestionDescriptionOption": "UseText"
        },
        "Choices": {
            "1": {"Display": "Left"},
            "2": {"Display": "Right"}
        },
        "Validation": {
            "Settings": {
                "ForceResponse": "ON"
            }
        }
    }

def add_question_to_block(survey_id, block_id, question_payload):
    url = f"{BASE_URL}/survey-definitions/{survey_id}/questions"
    q_response = requests.post(url, headers=HEADERS, json={"Question": question_payload})
    question_id = q_response.json()["result"]["QuestionID"]

    # Add question to block
    url_block = f"{BASE_URL}/survey-definitions/{survey_id}/blocks/{block_id}"
    response = requests.get(url_block, headers=HEADERS)
    block = response.json()["result"]
    block["BlockElements"].append({
        "Type": "Question",
        "QuestionID": question_id
    })

    requests.put(url_block, headers=HEADERS, json=block)

def build_survey(df, survey_name="NudgeLab"):
    survey_id = create_survey(survey_name)
    df_grouped = df.groupby(["url_0", "url_1"])

    for group_key, df_group in df_grouped:
        block_id = create_block(survey_id)

        for _, row in df_group.iterrows():
            payload = create_question_payload(row["exp"], row["image_0"], row["image_1"])
            add_question_to_block(survey_id, block_id, payload)

    print(f"Survey created: {survey_id}")

def main():
    parser = argparse.ArgumentParser(description="Generate Qualtrics survey.")
    parser.add_argument("--csv", type=str)
    args = parser.parse_args()

    df = pd.read_csv(args.csv)

    build_survey(df)

if __name__ == "__main__":
    main()
