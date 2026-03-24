class UserService:
    def get_user(self):
        repo = UserRepository()
        return repo.get_data()

class UserRepository:
    def get_data(self):
        return {"user": "data"}

def main():
    service = UserService()
    user = service.get_user()
    print(user)
