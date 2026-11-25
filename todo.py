import json
from pathlib import Path

DATA_FILE = Path(__file__).with_name("tasks.json")


def load_tasks(path=DATA_FILE):
    if not path.exists():
        return []
    tasks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise ValueError("数据应为任务列表")
    for task in tasks:
        if (not isinstance(task, dict)
                or not isinstance(task.get("title"), str)
                or not task["title"].strip()
                or type(task.get("done")) is not bool):
            raise ValueError("任务应包含非空 title 和布尔值 done")
    return tasks


def save_tasks(tasks, path=DATA_FILE):
    # 先完整写入临时文件，再替换原文件，减少写入失败造成的数据损坏。
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def task_index(text, count):
    try:
        number = int(text)
    except ValueError:
        raise ValueError("编号必须是整数。") from None
    if not 1 <= number <= count:
        raise ValueError(f"编号应在 1 到 {count} 之间。")
    return number - 1


def show_tasks(tasks):
    if not tasks:
        print("暂无任务。")
    for number, task in enumerate(tasks, start=1):
        status = "已完成" if task["done"] else "未完成"
        print(f"{number}. [{status}] {task['title']}")


def main():
    try:
        tasks = load_tasks()
    except (OSError, ValueError) as error:
        print(f"无法读取任务：{error}。请备份并检查 {DATA_FILE}，原文件未覆盖。")
        return 1
    while True:
        print("\n1 添加任务  2 查看任务  3 标记完成  0 退出")
        choice = input("请选择：").strip()
        if choice == "1":
            title = input("任务内容：").strip()
            if not title:
                print("任务内容不能为空。")
                continue
            tasks.append({"title": title, "done": False})
            save_tasks(tasks)
            print("已添加。")
        elif choice == "2":
            show_tasks(tasks)
        elif choice == "3":
            show_tasks(tasks)
            if not tasks:
                continue
            try:
                index = task_index(input("完成第几项："), len(tasks))
            except ValueError as error:
                print(error)
                continue
            if tasks[index]["done"]:
                print("该任务已经完成。")
                continue
            tasks[index]["done"] = True
            save_tasks(tasks)
            print("已标记完成。")
        elif choice == "0":
            print("再见！")
            return 0
        else:
            print("请输入菜单中的数字。")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EOFError, KeyboardInterrupt):
        print("\n已退出，已成功保存的任务会保留。")
    except OSError as error:
        print(f"保存失败：{error}。本次修改未保存，请检查目录权限和磁盘空间。")
        raise SystemExit(1)
