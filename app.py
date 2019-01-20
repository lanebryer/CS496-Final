from google.appengine.ext import ndb
import json
import webapp2
import urllib
import datetime
from google.appengine.api import urlfetch

def getEmail(authKey):
    googleUrl = 'https://www.googleapis.com/plus/v1/people/me'
    headers = {'Authorization': authKey}
    result = urlfetch.fetch(
        url=googleUrl,
        method=urlfetch.GET,
        headers=headers)
    result = json.loads(result.content)
    email = result["emails"][0]["value"]
    return email


class userAccount(ndb.Model):
    id = ndb.StringProperty()
    email = ndb.StringProperty(required=True)
    firstName = ndb.StringProperty(required=True)
    lastName = ndb.StringProperty(required=True)
    age = ndb.IntegerProperty(required=True)
    todos = ndb.KeyProperty(kind='todo', repeated=True)

    #custom to_dict code for KeyProperty taken from https://stackoverflow.com/questions/7721920/when-do-you-use-self-in-python
    #uses the urlsafe method on each key that is saved because the key format itself is not JSON serializable
    def custom_to_dict(self):
        return {
        "email": self.email,
        "firstName": self.firstName,
        "lastName": self.lastName,
        "age": self.age,
        "todos": [key.urlsafe() for key in self.todos]
        }

class todo(ndb.Model):
    id = ndb.StringProperty()
    body = ndb.StringProperty(required=True)
    dateCreated = ndb.StringProperty()
    dateToDo = ndb.StringProperty(required=True)
    owner = ndb.StringProperty()




class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.write("Landing page")

class Account(webapp2.RequestHandler):
    def get(self, id=None):
        email = getEmail(self.request.headers['Authorization'])
        accounts = userAccount.query().fetch()
        accountFound = False
        for account in accounts:
            if account.email == email:
                accountFound = True
                account_dict = account.custom_to_dict()
                #del account_dict["todos"]
                self.response.write(json.dumps(account_dict))

        if accountFound == False:
            self.response.status_int = 403
            self.response.write("ERROR 403: Your account was not found in the datastore")

    def post(self):
        parent_key = ndb.Key(userAccount, "parent_account")
        account_data = json.loads(self.request.body)
        email = getEmail(self.request.headers['Authorization'])
        firstNameExists = False
        lastNameExists = False
        ageExists = False
        toDoExists = False
        for i in account_data:
            if i == "firstName":
                firstNameExists = True
            elif i == "lastName":
                lastNameExists = True
            elif i == "age":
                ageExists = True
            elif i == "todos":
                toDoExists = True

        if firstNameExists == False or lastNameExists == False or ageExists == False:
            self.response.status_int = 403;
            self.response.write("ERROR 403: You must specify an email address, a first and last name, and an age")
        elif toDoExists == True:
            self.response.status_int = 403;
            self.response.write("ERROR 403: You cannot add to-do notes while creating an account");
        else:
            accountFound = False
            accounts = userAccount.query()
            for account in accounts:
                if account.email == account_data["email"]:
                    accountFound = True

            if accountFound == True:
                self.response.status_int = 403
                self.response.write("ERROR 403: An account with this email address already exists")
            else:
                if account_data["email"] != email:
                    self.response.write("ERROR 403: The email you input must match the email of the account you are signed in to")
                    self.response.status_int = 403
                else:
                    new_account = userAccount(email=email, firstName=account_data['firstName'], lastName=account_data['lastName'], age=account_data['age'], parent=parent_key)
                    new_account.put()
                    new_account.id = str(new_account.key.urlsafe())
                    new_account.put()
                    account_dict = new_account.to_dict()
                    del account_dict["todos"]
                    self.response.write(json.dumps(account_dict))

    def patch(self, id=None):
        if id:
            accountFound = False
            accounts = userAccount.query()
            for account in accounts:
                if account.id == id:
                    accountFound = True

            if accountFound == True:
                email = getEmail(self.request.headers['Authorization'])
                edited = False
                account = ndb.Key(urlsafe=id).get()
                if account.email == email:
                    patch_data = json.loads(self.request.body)
                    for item in patch_data:
                        if item == "firstName":
                            account.firstName = patch_data["firstName"]
                            edited = True

                        if item == "lastName":
                            account.lastName = patch_data["lastName"]
                            edited = True

                        if item == "age":
                            account.age = patch_data["age"]
                            edited = True

                        if item == "id" or item == "email" or item == "todos":
                            self.response.status_int = 403
                            self.response.write("ERROR 403: id and email are read-only values.  Todos should be edited individually.")
                            edited = False
                            break

                    if edited == True:
                        account.put()
                        account_dict = account.custom_to_dict()
                        self.response.write(json.dumps(account_dict))
                else:
                    self.response.status_int = 403
                    self.response.write("ERROR 403: You are not the owner of this account and cannot modify it")
            else:
                self.response.status_int = 403
                self.response.write("ERROR 403: ID not found")
        else:
            self.response.status_int = 403
            self.response.write("ERROR 403: Must provide account id to update")

    def delete(self, id=None):
        if id:
            email = getEmail(self.request.headers['Authorization'])
            accountFound = False
            accounts = userAccount.query()
            for account in accounts:
                if account.id == id:
                    accountFound = True
            if accountFound == True:
                account = ndb.Key(urlsafe=id).get()
                if account.email == email:
                    for item in account.todos:
                        item.delete()
                    account.key.delete()
                    self.response.status_int = 200
                    self.response.write("Account successfully deleted")
                else:
                    self.response.status_int = 403
                    self.response.write("You are not the owner of this account and cannot delete it")
            else:
                self.response.status_int = 403
                self.response.write("ERROR 403: ID not found")
        else:
            self.response.status_int = 403
            self.response.write("ERROR 403: ID not provided")

class todoHandler(webapp2.RequestHandler):
    def get(self, id=None):
        email = getEmail(self.request.headers['Authorization'])

        if id:
            todoFound = False
            todos = todo.query()
            for item in todos:
                if item.id == id:
                    todoFound = True
            if todoFound == True:
                foundTodo = ndb.Key(urlsafe=id).get()
                if foundTodo.owner == email:
                    todo_dict = foundTodo.to_dict()
                    todo_dict['self'] = "/todo/" + id
                    self.response.write(json.dumps(todo_dict))
                else:
                    self.response.status_int = 403
                    self.response.write("ERROR 403: You are not the owner of this todo note")
            else:
                self.response.status_int = 403
                self.response.write("ERROR 403: ID not found")
        else:
            todos = todo.query().fetch()
            todo_dicts = {"Results": []}
            for item in todos:
                if item.owner == email:
                    todo_data = item.to_dict()
                    todo_data['self'] = '/todo/' + item.key.urlsafe()
                    todo_dicts['Results'].append(todo_data)

            if len(todo_dicts["Results"]) == 0:
                self.response.write("You currently have no todo items")
            else:
                self.response.write(json.dumps(todo_dicts))

    def post(self):
        email = getEmail(self.request.headers['Authorization'])
        parent_key = ndb.Key(todo, "parent_todo")
        todo_data = json.loads(self.request.body)

        dateTodoExists = False
        bodyExists = False
        ownerExists = False
        dateCreatedExists = False

        for i in todo_data:
            if i == "body":
                bodyExists = True
            if i == "dateToDo":
                dateTodoExists = True
            if i == "owner":
                ownerExists = True
            if i == "dateCreated":
                dateCreatedExists = True

        if dateCreatedExists or ownerExists:
            self.response.status_int = 403
            self.response.write("ERROR 403: You cannot specify an owner or a creation date.  The creation date is automated and the owner will be assigned as your current account")
        else:
            if bodyExists and dateTodoExists:
                accounts = userAccount.query()
                accountFound = False
                for item in accounts:
                    if email == item.email:
                        new_todo = todo(owner=email, dateToDo=todo_data["dateToDo"], body = todo_data["body"], dateCreated = datetime.datetime.now().strftime("%m/%d/%Y"))
                        new_todo.put()
                        new_todo.id = str(new_todo.key.urlsafe())
                        new_todo.put()
                        todo_dict = new_todo.to_dict()
                        todo_dict['self'] = '/todo/' + new_todo.id
                        self.response.write(json.dumps(todo_dict))
                        accountFound = True
                        item.todos.append(new_todo.key)
                        item.put()

                if accountFound == False:
                    self.response.status_int = 403
                    self.response.write("ERROR 403: You do not currently have an account in the datastore.  Please make an account before trying to create a todo item")

    def delete(self, id=None):
        email = getEmail(self.request.headers['Authorization'])
        if id:
            todoFound = False
            todos = todo.query()
            for item in todos:
                if item.id == id:
                    todoFound = True

            if todoFound == True:
                foundTodo = ndb.Key(urlsafe=id).get()

                if foundTodo.owner == email:
                    foundTodo.key.delete()
                    self.response.status_int = 200
                    self.response.write("Todo deleted")

                    accounts = userAccount.query()
                    for account in accounts:
                        if account.email == email:
                            #code below finds the index of the key and then pops it off the list
                            #followed by updating the account with the missing todo
                            #taken from https://stackoverflow.com/questions/22819992/add-update-delete-from-a-ndb-keyproperty-google-cloud-datastore-ndb
                            pos = account.todos.index(ndb.Key(urlsafe=id))
                            account.todos.pop(pos)
                            account.put()

                else:
                    self.response.status_int = 403
                    self.response.write("ERROR 403: This todo does not belong to you")

            else:
                self.response.status_int = 403
                self.response.write("ERROR 403: ID not found")
        else:
            self.response.status_int = 403
            self.response.write("ERROR 403: ID not provided")

    def patch(self, id=None):
        if id:
            todoFound = False
            todos = todo.query()

            for item in todos:
                if item.id == id:
                    todoFound = True

            if todoFound == True:
                email = getEmail(self.request.headers['Authorization'])
                edited = False
                todoItem = ndb.Key(urlsafe=id).get()
                if todoItem.owner == email:
                    patch_data = json.loads(self.request.body)
                    for item in patch_data:
                        if item == "body":
                            todoItem.body = patch_data["body"]
                            edited = True

                        if item == "dateToDo":
                            todoItem.dateToDo = patch_data["dateToDo"]
                            edited = True

                        if item == "id" or item == "owner" or item == "dateCreated":
                            self.response.status_int = 403
                            self.response.write("ERROR 403: id, owner, and dateCreated are read-only values")
                            edited = False
                            break

                    if edited == True:
                        todoItem.put()
                        todo_dict = todoItem.to_dict()
                        self.response.write(json.dumps(todo_dict))
                else:
                    self.response.status_int = 403
                    self.response.write("ERROR 403: You are not the owner of this todo and cannot modify it")
            else:
                self.response.status_int = 403
                self.response.write("ERROR 403: ID not found")
        else:
            self.response.status_int = 403
            self.response.write("ERROR 403: Must provide todo id to update")

allowed_methods = webapp2.WSGIApplication.allowed_methods
new_allowed_methods = allowed_methods.union(('PATCH',))
webapp2.WSGIApplication.allowed_methods = new_allowed_methods

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/account', Account),
    ('/account/([A-z0-9\-]+)', Account),
    ('/todo', todoHandler),
    ('/todo/([A-z0-9\-]+)', todoHandler)
], debug=True)



