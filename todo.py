"""命令行待办事项：AI 协助开发的入门学习示例。"""

import json
from pathlib import Path

DATA_FILE = Path(__file__).with_name("tasks.json")


def load_tasks(path=DATA_FILE):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_tasks(tasks, path=DATA_FILE):
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def show_tasks(tasks):
    if not tasks:
        print("暂无任务。")
    for number, task in enumerate(tasks, start=1):
        status = "已完成" if task["done"] else "未完成"
        print(f"{number}. [{status}] {task['title']}")


def main():
    tasks = load_tasks()
    while True:
        print("\n1 添加任务  2 查看任务  3 标记完成  0 退出")
        choice = input("请选择：").strip()
        if choice == "1":
            tasks.append({"title": input("任务内容："), "done": False})
            save_tasks(tasks)
            print("已添加。")
        elif choice == "2":
            show_tasks(tasks)
        elif choice == "3":
            show_tasks(tasks)
            number = int(input("完成第几项："))
            tasks[number - 1]["done"] = True
            save_tasks(tasks)
            print("已标记完成。")
        elif choice == "0":
            print("再见！")
            break
        else:
            print("请输入菜单中的数字。")


if __name__ == "__main__":
    main()
