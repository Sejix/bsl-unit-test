"""Проверяет материалы навыка без запуска платформы 1С."""

import argparse
import json
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
BSL_BLOCK = re.compile(r"^```bsl\s*\n(.*?)^```\s*$", re.M | re.S)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
DIRECT_CALL = re.compile(
    r"\b(ЮТест|ЮТМетоды|ЮТЗапросы|Мокито|МокитоПерехват)\s*\.\s*(\w+)\s*\("
)
EXPORTED_METHOD = re.compile(
    r"^(?:Функция|Процедура)\s+(\w+)\s*\([^)]*\)\s+Экспорт", re.M
)

def render_template(template, values):

    missing = set(PLACEHOLDER.findall(template)) - values.keys()
    if missing:
        raise ValueError("Не заданы поля шаблона: " + ", ".join(sorted(missing)))

    return PLACEHOLDER.sub(lambda match: values[match[1]], template)

def sample_values(client=False, no_parameters=False):

    values = {
        "UUID": "22222222-2222-4222-8222-222222222222",
        "EXTENDED_CONFIGURATION_OBJECT_UUID": "11111111-1111-4111-8111-111111111111",
        "XML_VERSION": "2.21",
        "TEST_MODULE_NAME": "Тест_Расчеты",
        "TARGET_MODULE_NAME": "Расчеты",
        "TEST_NAME": "ПроверкаСуммы",
        "TEST_BODY": "\tРезультат = Расчеты.Сумма(2, 3);\n\tЮТест.ОжидаетЧто(Результат).Равно(5);",
        "REGISTER_METHOD": "ДобавитьКлиентскийТест" if client else "ДобавитьСерверныйТест",
        "MODULE_NAME": "ПоставщикДанных",
        "GLOBAL": "false",
        "CLIENT_MANAGED_APPLICATION": "true" if client else "false",
        "SERVER": "false" if client else "true",
        "EXTERNAL_CONNECTION": "false",
        "CLIENT_ORDINARY_APPLICATION": "false",
        "SERVER_CALL": "false",
        "PRIVILEGED": "false",
        "RETURN_VALUES_REUSE": "DontUse",
        "METHOD_NAME": "ПолучитьЗначение",
        "STUB_NAME": "ЮТПолучитьЗначение",
        "METHOD_DOCUMENTATION": "// Перехватывает получение значения для теста.",
        "SIGNATURE": "" if no_parameters else "Знач Ключ",
        "PARAMETERS_ARRAY_EXPRESSION": "Новый Массив" if no_parameters else "Мокито.МассивПараметров(Ключ)",
        "OWNER_EXPRESSION": "ПоставщикДанных",
        "FORWARD_ARGS": "" if no_parameters else "Ключ",
    }

    return values

def check_links(root, documents):

    for path, content in documents.items():
        for target in MD_LINK.findall(content):
            if re.match(r"(?:https?://|mailto:|#)", target):
                continue

            relative = unquote(target.split("#", 1)[0].strip("<>"))
            resolved = (path.parent / relative).resolve()
            if not resolved.is_relative_to(root) or not resolved.is_file():
                raise ValueError(f"Недоступная локальная ссылка: {path.relative_to(root)} -> {target}")

def check_evals(root):

    data = json.loads((root / "evals/evals.json").read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Описание сценариев должно быть объектом JSON")

    if data.get("skill_name") != "bsl-unit-test" or data.get("schema_version") != 2:
        raise ValueError("Неверное имя навыка или версия проверочных сценариев")

    cases = data["evals"]
    if not isinstance(cases, list) or not cases or not all(isinstance(case, dict) for case in cases):
        raise ValueError("Ожидается непустой список сценариев")

    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Сценарии отсутствуют или их идентификаторы повторяются")

    for case in cases:
        for field in ("prompt", "environment", "expected_output"):
            if not isinstance(case[field], str) or not case[field].strip():
                raise ValueError(f"Сценарий {case['id']}: не заполнено поле {field}")

        if not isinstance(case["should_trigger"], bool) or not isinstance(case["source_files"], dict):
            raise ValueError(f"Сценарий {case['id']}: неверные условия или исходные материалы")

        for name, content in case["source_files"].items():
            file_path = Path(name)
            if file_path.is_absolute() or ".." in file_path.parts or not isinstance(content, str):
                raise ValueError(f"Сценарий {case['id']}: неверное имя исходного файла")

        assertions = case["assertions"]
        if not isinstance(assertions, list) or not assertions or not all(isinstance(item, dict) for item in assertions):
            raise ValueError(f"Сценарий {case['id']}: ожидается непустой список критериев")

        if len({item["id"] for item in assertions}) != len(assertions):
            raise ValueError(f"Сценарий {case['id']}: пустые или повторяющиеся критерии")

        for item in assertions:
            if not all(isinstance(item[key], str) and item[key].strip() for key in ("id", "description", "check")):
                raise ValueError(f"Сценарий {case['id']}: не заполнен критерий")

    return cases

def check_templates(root):

    rendered_bsl = []
    count        = 0
    namespace    = {"md": "http://v8.1c.ru/8.3/MDClasses"}
    guidance     = (root / "references/templates.md").read_text(encoding="utf-8-sig")

    for path in sorted((root / "assets").glob("*.template")):
        template = path.read_text(encoding="utf-8-sig")
        for field in set(PLACEHOLDER.findall(template)):
            if f"`{field}`" not in guidance:
                raise ValueError(f"Не описано поле {field} из {path.name}")

        for client, no_parameters in ((False, False), (True, True)):
            rendered = render_template(template, sample_values(client, no_parameters))
            if "{{" in rendered or "}}" in rendered:
                raise ValueError(f"Незаполненное поле в {path.name}")

            if path.name.endswith(".xml.template"):
                document = ET.fromstring(rendered)
                module = document.find("md:CommonModule", namespace)
                if module is None:
                    raise ValueError(f"Нет общего модуля в {path.name}")

                uuid.UUID(module.attrib["uuid"])
                properties = module.find("md:Properties", namespace)
                for element in properties:
                    property_name = element.tag.split("}")[-1]
                    if property_name in ("Server", "ClientManagedApplication", "ClientOrdinaryApplication", "ServerCall"):
                        if element.text not in ("true", "false"):
                            raise ValueError(f"Неверный признак {property_name} в {path.name}")

            else:
                rendered_bsl.append(rendered)

            count += 1

    if not count:
        raise ValueError("Шаблоны отсутствуют")

    return count, rendered_bsl

def check_source_calls(source_root, code_blocks):

    calls = set()
    for code in code_blocks:
        calls.update(DIRECT_CALL.findall(code))
        calls.update(("ЮТТестовыеДанные", method) for method in re.findall(r"ЮТест\.Данные\(\)\.(\w+)\(", code))

    modules = {}
    for module, method in sorted(calls):
        if module not in modules:
            path = source_root / "CommonModules" / module / "Module.bsl"
            if not path.is_file():
                raise ValueError(f"Не найден исходный модуль {module}: {path}")

            modules[module] = set(EXPORTED_METHOD.findall(path.read_text(encoding="utf-8-sig")))

        if method not in modules[module]:
            raise ValueError(f"В переданных исходниках нет экспортного метода {module}.{method}")

    return len(calls)

def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", type=Path, default=Path(__file__).resolve().parents[1], help="Каталог навыка")
    parser.add_argument("--yaxunit-src", type=Path, help="Исходники движка с CommonModules и DataProcessors")
    arguments = parser.parse_args()
    root      = arguments.skill.resolve()

    try:
        documents  = {path: path.read_text(encoding="utf-8-sig") for path in root.rglob("*.md")}
        entrypoint = documents[root / "SKILL.md"]
        if not re.match(r"\A---\nname: bsl-unit-test\n", entrypoint):
            raise ValueError("Неверный заголовок SKILL.md")

        check_links(root, documents)
        cases = check_evals(root)
        template_count, blocks = check_templates(root)
        blocks.extend(block for content in documents.values() for block in BSL_BLOCK.findall(content))
        blocks.extend(content for case in cases for content in case["source_files"].values())

        print(f"Проверены локальные ссылки в {len(documents)} документах, {len(cases)} сценариев и {template_count} подстановок шаблонов.")
        if arguments.yaxunit_src:
            count = check_source_calls(arguments.yaxunit_src.resolve(), blocks)
            print(f"Подтверждено наличие {count} прямых вызовов и конструкторов данных в переданных исходниках.")

        print("Сборка и запуск на платформе 1С этой программой не выполняются.")
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as error:
        print(f"Ошибка проверки: {error}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
