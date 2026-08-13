# Шаблоны и placeholders

Используй шаблоны из `assets/`, чтобы не писать boilerplate заново.

## Новые тестовые модули

- `assets/test-common-module.bsl.template`
- `assets/test-common-module.xml.template`

Подставь:

- `{{TEST_MODULE_NAME}}` - имя нового тестового модуля;
- `{{TARGET_MODULE_NAME}}` - имя тестируемого модуля;
- `{{TEST_NAME}}` - первая тестовая процедура;
- `{{UUID}}` - UUID метаданных.

Не забудь добавить `<CommonModule>{{TEST_MODULE_NAME}}</CommonModule>` в
`Configuration.xml`.

## Заимствованный сторонний модуль под `&Вместо`

- `assets/adopted-common-module.xml.template`
- `assets/instead-stub.bsl.template`

Подставь:

- `{{MODULE_NAME}}` - borrowed-модуль;
- `{{EXTENDED_CONFIGURATION_OBJECT_UUID}}` - UUID из исходного XML объекта;
- `{{METHOD_NAME}}` - имя перехватываемого экспортного метода;
- `{{STUB_NAME}}` - имя процедуры расширения;
- `{{SIGNATURE}}` - сигнатура stub;
- `{{PARAMETERS_ARRAY}}` - аргументы для `Мокито.МассивПараметров(...)`;
- `{{FORWARD_ARGS}}` - аргументы для `ПродолжитьВызов(...)`.

## Генерация UUID

Подходит любой локальный генератор UUID. Примеры:

```powershell
[guid]::NewGuid()
```

```powershell
python -c "import uuid; print(uuid.uuid4())"
```

Если среда не позволяет запускать Python, используй PowerShell-генератор.

## Когда шаблонов достаточно

- создаешь новый тестовый CommonModule;
- заимствуешь ровно один сторонний CommonModule под `&Вместо`;
- нужен стандартный Мокито-интегрированный stub без дополнительной логики.
- в репозитории нет более подходящего готового тестового модуля, который надо
  просто расширить.

Если структура заметно отличается от шаблона, опирайся на шаблон как на
минимальный каркас, а не как на жесткое ограничение.
