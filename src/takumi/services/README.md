# Takumi services
## Intro
The purpose of the services is to represent the business model and isolate the database from the application.
This means that e.g. a query change shouldn't affect the application at all.

## API
### Static methods
All service GET and `create` methods are static.
```python
campaign = CampaignService.get_by_id(id)
new_campaign = CampaignService.create_campaign(**kwargs)
```

### Instance methods
All other POST and PUT methods are instance based. The service uses a context manager pattern that saves your transaction in
the end.
```python
with CampaignService(campaign) as service:
    service.update_description('The new description')
```

## Scoped session
The services are scope based, meaning a commit in one service instance won't affect another service transaction.
```python
post = PostService.get_by_id(post_id)
campaign = CampaignService.get_by_id(campaign_id)

# make some uncommitted changes
campaign.description = 'new description'
post.instructions = 'new instructions'

with CampaignService(campaign):
    # naturally we'd call a service method to update the description, but this is a proof of concept.
    pass
"""
^ this is the same as doing:
service = CampaignService(campaign)
service.save()
"""

# now the campaign description has been committed to the database, but the post changes are still dirty.
```

## Access to database
In order to fully isolate the database from the application the services need to make sure to *execute all queries
and statements*, never granting the controller access them.

## Permissions
The services should not know about the flask context, meaning that Takumi roles do not apply to services.
The views (i.e. GraphQL queries and mutations) should be context permission protected, but the services should be database protected.
The following could be a mock of the service permission:
```python
# graphql
@permissions.manage_influencers.require()
def mutate(root, info, **kwargs):
    with SomeService(instance) as service:
        service.update_instance()
```
```python
# service
class SomeService():
    @has_write_permission()
    def update_instance(self):
        ...
```
Community manager would have a `write_permission` on `update_instance`, but it's not flask context based.


Another way would be to pass in the permission as an argument:
```python
# graphql
@permissions.manage_influencers.require()
def mutate(root, info, **kwargs):
    with SomeService(instance) as service:
        service.update_instance(has_permission=permissions.update_instance.can())
```

The latter approach will have to do for now, since the first approach hasn't been implemented, yet.
