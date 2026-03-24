class UserService:
    def get_user(self):
        # Используем внешний класс
        repo = ExternalRepository()
        data = repo.fetch_data()
        return data
