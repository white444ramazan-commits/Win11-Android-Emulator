# Win11 Android Emulator

Проект настоящей виртуальной машины Windows 11 ARM64 для Android-планшетов. Это не макет рабочего стола Windows: основу проекта составляет открытый движок DroidVM с QEMU/crosvm, UEFI и встроенным VNC-клиентом.

## Состояние проекта

- Подключён исходный движок DroidVM как Git submodule в `engine/DroidVM` (зафиксированная версия upstream).
- Добавлены read-only диагностики аппаратной виртуализации от Root и обычного пользователя, а также отдельная инструкция по ограничениям Shizuku/rootless.
- Добавлен GitHub Actions workflow для сборки debug APK. CI build tested successfully with the upstream API 37 configuration; lowering compileSdk to API 36 causes Compose 1.12.0 dependency checks to fail.
- На первом этапе APK использует исходный интерфейс и package name DroidVM; отдельный фирменный интерфейс Win11 Android Emulator ещё не разработан.
- В upstream DroidVM документирован QEMU Software Emulation, но запуск его демона всё ещё требует Root. Shizuku не является Root; rootless-запуск требует переработки демона и процесса управления VM. См. [инструкцию по rootless/Shizuku](docs/ROOTLESS_AND_SHIZUKU.md).
- Сам факт успешной сборки APK **не означает**, что планшет сможет запустить VM: это зависит от доступности гипервизора в ядре и прав процесса.

## Совместимость с Redmi Pad 2 Pro

Твоя конфигурация: Snapdragon 7s Gen 4 (Qualcomm SM7635 Pro), ARM64, 8 ГБ RAM, 128 ГБ накопителя. DroidVM требует Android 13+, root и доступный `/dev/kvm`, `/dev/gunyah` или `/dev/gzvm`. В списке проверенных Qualcomm-платформ проекта указан Snapdragon 8 Gen 3 или новее; Snapdragon 7s Gen 4 отдельно не заявлен. Поэтому совместимость пока **не подтверждена**.

Сначала выполни диагностику из [`docs/REDMI_PAD_2_PRO.md`](docs/REDMI_PAD_2_PRO.md). Не прошивай ядро и не меняй boot-раздел ради этой проверки.

## Получить исходники

```bash
git clone --recurse-submodules https://github.com/white444ramazan-commits/Win11-Android-Emulator.git
cd Win11-Android-Emulator
```

Если репозиторий уже клонирован без submodule:

```bash
git submodule update --init --recursive
```

## Собрать APK

Нужны Android Studio/SDK, JDK 17 или совместимый с upstream Gradle JDK, Android SDK Platform 37, NDK и CMake 3.22.1+. Проще всего открыть `engine/DroidVM` в Android Studio. Из терминала:

```bash
./scripts/build-apk.sh
```

Готовый debug APK появится в `engine/DroidVM/app/build/outputs/apk/debug/`. Также GitHub Actions собирает APK и публикует его как artifact после push.

## Образ Windows

Нужен официальный **Windows 11 Arm64 ISO**, а не x64 ISO. Скачать его можно на [официальной странице Microsoft](https://www.microsoft.com/software-download/windows11arm64). Для активации Windows требуется соответствующая лицензия.

Минимальные требования Windows 11 для VM включают 4 ГБ RAM, 64 ГБ диска, два виртуальных процессора и UEFI/TPM/Secure Boot-настройки. На планшете с 8 ГБ физической RAM это будет тесная конфигурация: Android и VM будут конкурировать за память. Виртуальный диск лучше делать динамическим, но ему всё равно нужно свободное место по мере установки и обновлений.

## Структура

```text
engine/DroidVM/       upstream VM manager and QEMU/crosvm integration
docs/                 device compatibility and setup notes
scripts/              Android diagnostics and build helper
.github/workflows/    APK CI build
```

## Лицензии

Подключённый движок DroidVM распространяется под GPL-3.0; его лицензия и сведения о сторонних компонентах находятся в `engine/DroidVM`. Сохраняй notices и лицензии при модификации или распространении сборок.
