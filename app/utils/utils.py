import json
import re
from io import StringIO
from typing import Optional

import pandas as pd

from app.utils.enumeration import ACTION, MODEL_TYPE
from app.utils.exceptions import FormatMismatchError, ToolNotFoundError

def wtqtb2df(wtq_tb: dict) -> pd.DataFrame:
    """This function will convert a table dict to a pandas dataframe with correct data type (auto infer)."""
    header, rows = wtq_tb["header"], wtq_tb["rows"]
    df = pd.DataFrame(data=rows, columns=header)
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    df_new = pd.read_csv(StringIO(buffer.getvalue()))
    df_dtype_converted = df_new.convert_dtypes()

    return df_dtype_converted


def sqltb2json(wtq_tb: dict, add_row_number: bool, lower_case: bool):
    df = wtqtb2df(wtq_tb)

    table_json = {}
    for idx, (_, row) in enumerate(df.iterrows()):
        row_dict = row.to_dict()
        if add_row_number:
            row_number_col = "row number" if lower_case else "Row Number"
            row_number = row[row_number_col]
            del row_dict[row_number_col]
        else:
            row_number = idx + 1
        table_json[row_number] = row_dict

    formatted_table_json = "{\n"
    for k, v in table_json.items():
        formatted_table_json += f'  "{k}":{json.dumps(v, separators=(",", ":"))},\n'
    formatted_table_json = formatted_table_json.rstrip(",\n") + "\n}"

    return formatted_table_json


def sqltb2markdown(wtq_tb: dict):
    df = wtqtb2df(wtq_tb)

    return df.to_markdown(index=False)


def sqltb2html(wtq_tb: dict):
    df = wtqtb2df(wtq_tb)

    table_html = df.to_html(index=False, bold_rows=False, border=0, escape=False)
    # remove style attr
    table_html = re.sub(r'\s*style\s*=\s*"[^"]*"', "", table_html)

    # remove class attr
    table_html = re.sub(r'\s*class\s*=\s*"[^"]*"', "", table_html)
    table_html = re.sub(r"(</th>)\s+(<th>)", r"\1\2", table_html)
    table_html = re.sub(r"(</td>)\s+(<td>)", r"\1\2", table_html)

    table_html = re.sub(r"(<tr>)\s+(<th>)", r"\1\2", table_html)
    table_html = re.sub(r"(</th>)\s+(</tr>)", r"\1\2", table_html)
    table_html = re.sub(r"(<tr>)\s+(<td>)", r"\1\2", table_html)
    table_html = re.sub(r"(</td>)\s+(</tr>)", r"\1\2", table_html)

    return table_html


def sqltb2dfloader(wtq_tb: dict):
    df = wtqtb2df(wtq_tb)

    col_vals = []
    for col in df.columns:
        # print(col)
        vals = df[col].tolist()
        # vals = [f"'{val}'" if df[col].dtype == "string[python]" else f"{val}" for val in vals]
        col_vals.append(f'"{col}": {vals}')

    col_vals = ",\n    ".join(col_vals)

    tb_dfloader = f"pd.DataFrame({{\n    {col_vals}\n}})"
    return tb_dfloader


def parse_think(gpt_msg: str) -> str:
    """
    Extract the thoughts from the agent by looking for <scratchpad> tag.
    
    Args: 
        gpt_msg: The message from the agent
        
    Returns:
        The extracted thought as a string
    """
    pattern = r"<scratchpad>(.*?)</scratchpad>"
    match = re.search(pattern, gpt_msg, re.DOTALL)
    if not match:
        return "No explicit thought provided"
    
    return match.group(1).strip()

def parse_answer(gpt_msg):
    pattern = r"Finish:(.+)"

    match = re.search(pattern, gpt_msg)
    if not match:
        raise FormatMismatchError()
    ans = match.group(1).strip()
    if "Done!" in ans:
        return "Done!"
    # get final answer
    pattern = r"answer\((.*?)\)"
    match = re.search(pattern, ans)
    if not match:
        raise FormatMismatchError()

    return match.group(1).strip()


def get_model_token_limit(model: MODEL_TYPE) -> Optional[int]:
    if model == MODEL_TYPE.GPT_3_5_TURBO:
        return 4096
    if model == MODEL_TYPE.GPT_4:
        return 8192
    if model == MODEL_TYPE.GPT_3_5_TURBO_1106:
        return 16385
    if model == MODEL_TYPE.GPT_4_1106:
        return 128000
    if model.value.startswith("claude-3"):
        return 200000
    return None


def count_tokens_openai_chat_models(messages, encoding) -> int:
    num_tokens = 0
    for message in messages:
        # message follows <im_start>{role/name}\n{content}<im_end>\n
        num_tokens += 4
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens
