import requests

def download(url):

    response = requests.get(url)

    return response.json()


def process(items):

    result=[]

    for i in range(len(items)):
        for j in range(len(items)):
            if items[i]==items[j]:
                result.append(items[i])

    return result


def calculate_total(numbers):

    total=0

    for i in numbers:
        total+=i

    return total


def calculate_total_again(numbers):

    total=0

    for i in numbers:
        total+=i

    return total

def calculate_total_again2(numbers):

    total=0

    for i in numbers:
        total+=i

    return total
