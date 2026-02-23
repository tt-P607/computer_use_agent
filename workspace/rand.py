import random

def guess_number_game():
    # 生成 1-100 的随机整数
    target = random.randint(1, 100)
    count = 0
    print("我已经想好了一个 1-100 之间的数字，快来猜吧！")
    
    while True:
        try:
            guess = int(input("请输入你的猜测："))
            count += 1
            if guess < target:
                print("小了～再试试更大的数字！")
            elif guess > target:
                print("大了～再试试更小的数字！")
            else:
                print(f"猜中啦！答案就是 {target}，你一共猜了 {count} 次～")
                break
        except ValueError:
            print("请输入一个有效的整数哦！")

if __name__ == "__main__":
    guess_number_game()