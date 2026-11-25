"""命令行待办事项：AI 协助开发的入门学习示例。"""


def show_tasks(tasks):
    if not tasks:
        print("暂无任务。")
    for number, task in enumerate(tasks, start=1):
        print(f"{number}. {task}")


def main():
    tasks = []
    while True:
        print("\n1 添加任务  2 查看任务  0 退出")
        choice = input("请选择：").strip()
        if choice == "1":
            tasks.append(input("任务内容："))
            print("已添加。")
        elif choice == "2":
            show_tasks(tasks)
        elif choice == "0":
            print("再见！")
            break
        else:
            print("请输入菜单中的数字。")


if __name__ == "__main__":
    main()
