# GraphQL
## Introduction
The purpose of this doc is to establish some set of ground rules for the graphql project.

## Mutations

### `mutate` function
The `mutate` function should have the following parameters:
```python
def mutate(root, info, ...):
    pass
```
The graphene docs often mix up `root` with `self`, but this function is actually static. So in order to not cause any misconception, we should use `root`.

### When to create a new object mutation?
Those mutation which change the state should have their own unique mutations. The proof of concept there is that it shouldn't be possible to add multiple state changing arguments to a single mutation. Which of these arguments should make the first state transition?

There is a fine line of when to create a new class object mutation and when you should gather the mutations. 
The mutations should never be bound to what the client wants to do. In this example, we'll use a `campaign` instance and the following mutate actions: `has_nda`, `set_push_notification_message`, and `launch`. As far as the client is concerned, these are three different mutations, but two of them should be grouped together since they're both updating fields of the `campaign` instance with no side effects. That would be `has_nda` and `set_push_notification_message`. The following should represent its mutation:
```python
class UpdateCampaign(BaseObjectMutation):
    class Arguments:
        id = arguments.UUID(required=True)

        has_nda = arguments.Boolean()
        push_notification_message = arguments.Boolean()

    campaign = fields.Field('campaign')

    # probably use **kwargs
    def mutate(root, info, id, has_nda=None, push_notification_message=None):
        if has_nda is not None:
            ...
        if push_notification_message is not None:
            ...
```
However, `launch` will change the campaign's state, transitioning from `draft` to `launched`. That should be a different mutation with its own object mutation class.

### Arguments
The arguments represent the view models.
All arguments should come from `takumi.graphql.arguments`:
```python
id = arguments.UUID(required=True)
```

### What should mutations return?
The mutations should always return `fields`, or DTOs (Data-To-Objects). This is the distinction between `arguments` and `fields`.
```python
class SomeClass(BaseObjectMutation):
    class Arguments:
        some_args = arguments.String()

    to_return = fields.String()
```

## Queries

## Types
All types should come from `takumi.graphql.fields`:
```python
id = fields.UUID()
```

## Exceptions
@axel
